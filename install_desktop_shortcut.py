"""Create or refresh a durable Windows desktop shortcut for this folder."""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def create_shortcut():
    redirected=os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    desktop=(Path(redirected) / "Desktop") if redirected and (Path(redirected) / "Desktop").exists() else (Path.home() / "Desktop")
    link=desktop / "Homework & Document Studio.lnk"
    def ps_quote(value):
        tick=chr(96)
        return '"' + str(value).replace(tick,tick*2).replace('"',tick+'"') + '"'
    script=('$shell=New-Object -ComObject WScript.Shell;$s=$shell.CreateShortcut('+ps_quote(link)+');'
            '$s.TargetPath='+ps_quote(sys.executable)+';$s.Arguments='+ps_quote('"'+str(ROOT/"run_studio.py")+'"')+
            ';$s.WorkingDirectory='+ps_quote(ROOT)+';$s.IconLocation='+ps_quote(ROOT/"assets"/"studio_logo.ico")+
            ';$s.Description='+ps_quote("Open the offline Homework & Document Studio")+';$s.Save()')
    subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",script],check=True,capture_output=True)
    return link
if __name__ in ("__main__","__shortcut_installer__"): create_shortcut()
