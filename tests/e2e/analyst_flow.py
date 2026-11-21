"""Exercise an isolated, running InvestWatch demo with Playwright and its real API.

Pass the URL of a disposable instance. This test saves a decision and uploads a short clip.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from uuid import uuid4

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def run(base, binary, captures):
    with sync_playwright() as p:
        options={"args":["--no-sandbox"]}
        if binary:
            options["executable_path"]=str(binary)
        browser=p.chromium.launch(**options)
        page=browser.new_page(viewport={"width":1440,"height":990})
        errors=[]
        page.on("pageerror",lambda err: errors.append(str(err)))
        page.goto(base,wait_until="networkidle")
        page.get_by_role("button",name=re.compile("Otwórz przykład z nagrania")).click()
        btn=page.locator(".timecode").first
        btn.wait_for()
        page.wait_for_function("document.querySelector('video')?.readyState >= 1")
        btn.click()
        page.wait_for_function("document.querySelector('video').currentTime >= 4.30")
        page.locator("video").evaluate("(v)=>v.pause()")
        assert page.get_by_text("94 / 100").count()>0
        assert page.get_by_text("Sam opis").is_visible()
        page.get_by_role("button",name="Decyzja i historia").click()
        page.locator("#decision").select_option("reviewing")
        note="Sprawdzono cytat i czas · "+uuid4().hex[:6]
        page.locator("#note").press_sequentially(note,delay=8)
        assert page.locator("#note").input_value()==note
        page.get_by_role("button",name="Zapisz decyzję").click()
        page.wait_for_function("document.body.innerText.includes('Zapisano decyzję') || document.body.innerText.includes('Decyzja została zapisana')")
        case=page.request.get(base+"/v1/cases/demo-studio-aurora").json()
        assert case["status"]=="reviewing" and any(h["note"]==note for h in case["history"])
        resp=page.request.patch(base+"/v1/cases/demo-studio-aurora",data={"status":"closed","note":"stale","expectedRevision":1})
        assert resp.status==409
        page.get_by_role("button",name="Umowa / aneks").click()
        page.get_by_role("button",name="Przygotuj pytanie",exact=True).click()
        page.get_by_text(re.compile("Czy firma rozpoznaje"),exact=False).first.wait_for()
        for action in ["waiting","documents"]:
            current=page.request.get(base+"/v1/cases/demo-studio-aurora").json()
            response=page.request.post(base+"/v1/cases/demo-studio-aurora/inquiry",
                                      data={"action":action,"expectedRevision":current["revision"]})
            assert response.ok,response.text()
        for end,aligned in [("2026-11-15",False),("2026-11-30",True)]:
            c=page.request.get(base+"/v1/cases/demo-studio-aurora").json()
            result=page.request.post(base+"/v1/cases/demo-studio-aurora/contract",
                data={"endDate":end,"expectedRevision":c["revision"],"label":"Umowa testowa","channel":"Studio","requiredLabel":"reklama"})
            assert result.ok and result.json()["aligned"]==aligned and len(result.json()["comparisons"])==3
        page.reload(wait_until="networkidle")
        state=page.request.get(base+"/v1/state").json()
        second=next(f for f in state["findings"] if f["id"]=="demo-aurora-kod")
        assert second["modalityComparison"]["descriptionOnly"]==12 and second["modalityComparison"]["withAudio"]==74
        assert second["possibleUndisclosedPromotion"]
        # Reach the single-mention case through the normal search path.
        page.get_by_role("searchbox").fill(second["title"])
        page.get_by_role("button",name=re.compile(re.escape(second["title"]))).last.click()
        page.locator(".timecode").first.click()
        assert "otwórz rachunek" in page.locator(".detail").inner_text().lower()
        captures.mkdir(parents=True,exist_ok=True)
        page.locator(".detail").scroll_into_view_if_needed()
        page.locator(".detail").screenshot(path=str(captures/"single-mention-desktop.png"))
        m2=next(f for f in state["findings"] if f.get("id")=="dom-xtb-etf")
        assert len(m2["checks"])==19
        page.get_by_role("searchbox").fill(m2["title"])
        page.get_by_role("button",name=re.compile(re.escape(m2["title"]))).last.click()
        page.locator(".detail img").first.wait_for()
        assert page.locator(".detail img").first.evaluate("(i)=>i.complete && i.naturalWidth>0")
        page.get_by_role("button",name=re.compile("Jakość analizy")).first.click()
        slider=page.get_by_role("slider")
        slider.focus()
        slider.press("End")
        assert slider.input_value()=="100"
        hi=page.request.get(base+"/v1/calibration?threshold=100").json()
        lo=page.request.get(base+"/v1/calibration?threshold=30").json()
        assert hi["n"]==lo["n"]==13 and (hi["fp"],hi["fn"])!=(lo["fp"],lo["fn"])
        page.get_by_role("button",name=re.compile("Źródła")).first.click()
        assert "peer" in page.locator("main").inner_text().lower()
        page.get_by_role("button",name=re.compile("Własne nagranie")).first.click()
        name="Próba uploadu "+uuid4().hex[:6]
        # A new container with a different hash forces actual inference, not the replay transcript.
        with tempfile.TemporaryDirectory() as temp:
            clip=Path(temp)/"nowa-proba.wav"
            subprocess.run(["ffmpeg","-loglevel","error","-i",str(ROOT/"analysis/media/wezwanie.mp4"),
                "-map","0:a:0","-ar","16000","-ac","1",str(clip)],check=True)
            page.locator("#upload-title").fill(name)
            page.locator("#upload-description").fill("Edukacyjna rozmowa o budżecie")
            page.locator("#upload-file").set_input_files(str(clip))
            page.get_by_role("button",name="Prześlij do analizy").click()
        limit=time.monotonic()+55
        while time.monotonic()<limit:
            state=page.request.get(base+"/v1/state").json()
            matches=[f for f in state["findings"] if f.get("title")==name]
            if matches:
                break
            page.wait_for_timeout(400)
        assert matches and matches[0]["segments"] and matches[0]["signalType"]=="brand_cta"
        media=page.request.get(base+matches[0]["mediaUrl"],headers={"Range":"bytes=0-31"})
        assert media.status==206 and len(media.body())==32
        page.set_viewport_size({"width":390,"height":844})
        page.reload(wait_until="networkidle")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+1")
        page.screenshot(path=str(captures/"queue-mobile.png"))
        assert not errors,errors
        browser.close()
        return {"browser":"Chromium","jsErrors":errors,"newUploadASR":matches[0]["segments"],
                "singleMention":second["modalityComparison"],"m2Controls":len(m2["checks"]),
                "calibrationN":hi["n"],"mediaRange":media.status,"mobileWidth":390}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--chromium",type=Path)
    parser.add_argument("--out",type=Path,default=ROOT/".runtime/browser")
    args=parser.parse_args()
    print(json.dumps(run(args.url.rstrip("/"),args.chromium,args.out),ensure_ascii=False,indent=2))
