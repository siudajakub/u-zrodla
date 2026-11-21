"""Serwis scheduler: zleca skan live co INVESTWATCH_SCHEDULE_INTERVAL sekund (rola CronJob z briefu §3.1).

Nie wykonuje skanu. Zapisuje zadanie do trwałego dziennika skanów i kolejki (api.jobs.submit), a wykonuje je worker.
Identyfikator `scheduled-<okres>-<numer okna>` jest ten sam co w dotychczasowej pętli workera, więc powtórne
zlecenie w tym samym oknie (restart, dwa schedulery) nie tworzy drugiego skanu. Interwał 0 = wyłączony.
Zdrowie: znacznik /tmp/scheduler.beat odświeżany co 30 s.
"""
import logging
import os
from pathlib import Path
import signal
import time

BEAT = Path(os.environ.get("INVESTWATCH_SCHEDULER_BEAT", "/tmp/scheduler.beat"))
TICK = 30


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s scheduler %(message)s")
    log = logging.getLogger("investwatch.scheduler")
    interval = int(os.environ.get("INVESTWATCH_SCHEDULE_INTERVAL") or 0)
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    from api import jobs, store  # noqa: E402  (import po konfiguracji logów; tworzy schemat, jeśli go nie ma)
    store.init()
    log.info("start: okres %s s%s", interval, "" if interval > 0 else " (wyłączony)")
    window = None
    while not stop:
        now = time.time()
        if interval > 0 and int(now // interval) != window:
            window = int(now // interval)
            try:
                scan = jobs.submit("live", f"scheduled-{interval}-{window}")
                log.info("zlecono skan %s (%s)", scan["id"], scan["status"])
            except Exception:  # baza chwilowo zajęta: spróbuj w kolejnym takcie
                log.exception("nie udało się zlecić skanu")
                window = None
        BEAT.touch()
        for _ in range(TICK):
            if stop:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
