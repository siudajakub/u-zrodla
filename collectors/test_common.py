from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from collectors.common import (
    DEFAULT_USER_AGENTS, Identity, SourceError, configured_proxies, configured_user_agents,
    is_loopback, open_url, redact_proxy,
)


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


def stop(server):
    server.shutdown()
    server.server_close()


def recorder(status=200, body=b"ok", headers=()):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append({"path": self.path, "ua": self.headers.get("User-Agent"), "host": self.headers.get("Host")})
            self.send_response(status)
            for key, value in headers:
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_CONNECT(self):
            seen.append({"connect": self.path})
            self.send_error(502)

        def log_message(self, *args):
            pass

    server = serve(Handler)
    return server, seen


class UserAgentTests(unittest.TestCase):
    def test_defaults_identify_investwatch_with_version(self):
        self.assertGreaterEqual(len(DEFAULT_USER_AGENTS), 3)
        self.assertTrue(all(ua.startswith("InvestWatch-SourceMonitor/") for ua in DEFAULT_USER_AGENTS))

    def test_pool_from_variable_and_file_and_fallback(self):
        self.assertEqual(configured_user_agents({"INVESTWATCH_USER_AGENTS": "A/1|B/2\nA/1\n bad\x00ua "}), ("A/1", "B/2"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "agents.txt")
            path.write_text("# comment\nC/3\n\nD/4\n", encoding="utf-8")
            self.assertEqual(configured_user_agents({"INVESTWATCH_USER_AGENTS_FILE": str(path)}), ("C/3", "D/4"))
            self.assertEqual(configured_user_agents({"INVESTWATCH_USER_AGENTS_FILE": str(path) + ".missing"}), DEFAULT_USER_AGENTS)
        self.assertEqual(configured_user_agents({}), DEFAULT_USER_AGENTS)

    def test_one_agent_per_host_for_the_whole_session_and_rotation_across_hosts_and_sessions(self):
        identity = Identity(agents=[f"UA/{i}" for i in range(4)], proxies=(), session="one")
        hosts = [f"host{i}.example" for i in range(40)]
        first = {h: identity.user_agent(h) for h in hosts}
        self.assertEqual(first, {h: identity.user_agent(h) for h in hosts})
        self.assertEqual(identity.user_agent("HOST0.example"), first["host0.example"])
        self.assertGreater(len(set(first.values())), 1)
        identity.new_session("two")
        second = {h: identity.user_agent(h) for h in hosts}
        self.assertEqual(second, {h: identity.user_agent(h) for h in hosts})
        self.assertNotEqual(first, second)

    def test_request_carries_the_session_agent(self):
        server, seen = recorder()
        identity = Identity(agents=["Only/1"], proxies=())
        self.assertEqual(open_url(f"http://127.0.0.1:{server.server_port}/a", identity), b"ok")
        self.assertEqual(seen[0]["ua"], "Only/1")
        stop(server)


class ProxyTests(unittest.TestCase):
    def test_parsing_and_loopback(self):
        self.assertEqual(configured_proxies({"INVESTWATCH_PROXIES": "http://a:8080, ftp://x:1 junk http://a:8080 https://b:3128"}),
                         ("http://a:8080", "https://b:3128"))
        self.assertEqual(configured_proxies({}), ())
        self.assertTrue(all(is_loopback(h) for h in ("127.0.0.1", "localhost", "::1", "[::1]", "x.localhost")))
        self.assertFalse(is_loopback("example.org"))
        self.assertEqual(redact_proxy("http://user:secret@proxy.example:8080"), "http://proxy.example:8080")

    def test_request_goes_through_the_proxy_and_rotates_over_a_dead_one(self):
        proxy, via = recorder(body=b"from-proxy")
        dead = "http://127.0.0.1:1"
        live = f"http://127.0.0.1:{proxy.server_port}"
        identity = Identity(agents=["U/1"], proxies=(dead, live))
        self.assertEqual(open_url("http://upstream.invalid/page?q=1", identity), b"from-proxy")
        self.assertEqual(via[0]["path"], "http://upstream.invalid/page?q=1")  # absolute URI: it was the proxy
        self.assertEqual(via[0]["ua"], "U/1")
        self.assertIn(dead, identity.down)
        self.assertEqual(open_url("http://upstream.invalid/again", identity), b"from-proxy")
        self.assertEqual(len(via), 2)
        stop(proxy)

    def test_proxy_rotation_is_round_robin(self):
        first, seen_first = recorder(body=b"1")
        second, seen_second = recorder(body=b"2")
        identity = Identity(agents=["U/1"], proxies=(f"http://127.0.0.1:{first.server_port}", f"http://127.0.0.1:{second.server_port}"))
        bodies = [open_url(f"http://upstream.invalid/{i}", identity) for i in range(4)]
        self.assertEqual(sorted(bodies), [b"1", b"1", b"2", b"2"])
        stop(first)
        stop(second)

    def test_loopback_target_never_uses_the_proxy(self):
        proxy, via = recorder(body=b"from-proxy")
        target, direct = recorder(body=b"direct")
        identity = Identity(agents=["U/1"], proxies=(f"http://127.0.0.1:{proxy.server_port}",))
        self.assertEqual(open_url(f"http://127.0.0.1:{target.server_port}/x", identity), b"direct")
        self.assertEqual(via, [])
        self.assertEqual(len(direct), 1)
        stop(proxy)
        stop(target)

    def test_all_proxies_down_stops_without_silent_direct_connection(self):
        identity = Identity(agents=["U/1"], proxies=("http://127.0.0.1:1",))
        with self.assertRaises(SourceError):
            open_url("http://upstream.invalid/", identity)
        with self.assertRaises(SourceError) as raised:
            open_url("http://upstream.invalid/", identity)
        self.assertIn("proxy", str(raised.exception).lower())

    def test_https_through_a_refusing_proxy_marks_it_down(self):
        proxy, via = recorder()
        address = f"http://127.0.0.1:{proxy.server_port}"
        identity = Identity(agents=["U/1"], proxies=(address,))
        with self.assertRaises(SourceError):
            open_url("https://upstream.invalid/", identity)
        self.assertEqual(via[0]["connect"], "upstream.invalid:443")
        self.assertIn(address, identity.down)
        stop(proxy)

    def test_without_proxies_behaviour_is_unchanged(self):
        server, seen = recorder(body=b"plain")
        identity = Identity(agents=["U/1"], proxies=())
        self.assertEqual(open_url(f"http://127.0.0.1:{server.server_port}/p", identity), b"plain")
        self.assertEqual(seen[0]["path"], "/p")
        stop(server)


class BackoffTests(unittest.TestCase):
    def test_429_sets_backoff_and_does_not_retry_under_another_identity(self):
        server, seen = recorder(status=429, headers=[("Retry-After", "7")])
        clock = [1000.0]
        identity = Identity(agents=["A/1", "B/2", "C/3"], proxies=(), session="s", clock=lambda: clock[0])
        url = f"http://127.0.0.1:{server.server_port}/blocked"
        host = "127.0.0.1"
        agent = identity.user_agent(host)
        with self.assertRaises(SourceError) as first:
            open_url(url, identity)
        self.assertEqual((first.exception.status, first.exception.retry_after), (429, 7))
        with self.assertRaises(SourceError) as second:
            open_url(url, identity)
        self.assertEqual(len(seen), 1)  # the second attempt never reached the network
        self.assertIn("wstrzymane", str(second.exception))
        self.assertEqual(identity.user_agent(host), agent)
        clock[0] += 8
        with self.assertRaises(SourceError):
            open_url(url, identity)
        self.assertEqual(len(seen), 2)  # after the backoff the same identity tries again
        self.assertEqual({row["ua"] for row in seen}, {agent})
        stop(server)

    def test_403_and_default_backoff_cap(self):
        server, seen = recorder(status=403)
        identity = Identity(agents=["A/1"], proxies=())
        with self.assertRaises(SourceError) as raised:
            open_url(f"http://127.0.0.1:{server.server_port}/", identity)
        self.assertEqual(raised.exception.status, 403)
        self.assertEqual(raised.exception.retry_after, 300)
        self.assertEqual(identity.block("x.example", 10 ** 9), 3600)
        stop(server)

    def test_404_does_not_start_a_backoff(self):
        server, seen = recorder(status=404)
        identity = Identity(agents=["A/1"], proxies=())
        for _ in range(2):
            with self.assertRaises(SourceError):
                open_url(f"http://127.0.0.1:{server.server_port}/", identity)
        self.assertEqual(len(seen), 2)
        stop(server)

    def test_keep_errors_returns_status_and_headers_for_diagnosis(self):
        server, _ = recorder(status=302, headers=[("Location", "https://example.org/accounts/login/")])
        status, headers, body = open_url(f"http://127.0.0.1:{server.server_port}/", Identity(agents=["A/1"], proxies=()), keep_errors=True)
        self.assertEqual((status, headers["Location"], body), (302, "https://example.org/accounts/login/", b"ok"))
        stop(server)


if __name__ == "__main__":
    unittest.main()
