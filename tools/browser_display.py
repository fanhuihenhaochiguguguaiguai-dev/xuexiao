from pathlib import Path
from contextlib import contextmanager
import os,secrets,signal,subprocess,tempfile,time
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'.cache';WORK.mkdir(exist_ok=True)
# Existing installed Xorg dummy driver, authenticated and local-only.
CONFIG='''Section "ServerFlags"
 Option "AutoAddDevices" "false"
 Option "AutoAddGPU" "false"
 Option "DontVTSwitch" "true"
EndSection
Section "Device"
 Identifier "LabDummy"
 Driver "dummy"
 VideoRam 192000
EndSection
Section "Monitor"
 Identifier "LabMonitor"
 HorizSync 10-200
 VertRefresh 30-200
 Modeline "1280x720" 74.25 1280 1390 1430 1650 720 725 730 750 +HSync +VSync
EndSection
Section "Screen"
 Identifier "LabScreen"
 Device "LabDummy"
 Monitor "LabMonitor"
 DefaultDepth 24
 SubSection "Display"
  Depth 24
  Modes "1280x720"
 EndSubSection
EndSection
Section "ServerLayout"
 Identifier "LabLayout"
 Screen "LabScreen"
EndSection
'''
@contextmanager
def display():
    if os.environ.get('DISPLAY'):yield dict(os.environ);return
    number=next(n for n in range(97,110) if not Path(f'/tmp/.X11-unix/X{n}').exists() and not Path(f'/tmp/.X{n}-lock').exists());server=None
    try:
        with tempfile.TemporaryDirectory(prefix='campus-display-',dir=WORK) as directory:
            work=Path(directory);config=work/'xorg.conf';config.write_text(CONFIG);auth=work/'authority';auth.touch(mode=0o600)
            subprocess.run(['xauth','-f',str(auth),'add',f':{number}','.',secrets.token_hex(16)],check=True,capture_output=True,timeout=10)
            with (work/'server.log').open('w') as log:
                server=subprocess.Popen(['/usr/lib/xorg/Xorg',f':{number}','-config',str(config),'-auth',str(auth),'-nolisten','tcp','-noreset','-novtswitch','-sharevts','-logfile',str(work/'Xorg.log')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                end=time.monotonic()+10
                while not Path(f'/tmp/.X11-unix/X{number}').exists():
                    if server.poll() is not None or time.monotonic()>end:raise RuntimeError('Temporary display unavailable')
                    time.sleep(.1)
                yield dict(os.environ,DISPLAY=f':{number}',XAUTHORITY=str(auth),LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',OMP_NUM_THREADS='2')
    finally:
        if server and server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait(timeout=5)
ARGS=['--no-sandbox','--disable-gpu-sandbox','--enable-unsafe-webgpu','--enable-unsafe-swiftshader','--use-angle=swiftshader','--enable-features=Vulkan','--use-vulkan=swiftshader','--disable-vulkan-surface','--disable-dev-shm-usage','--num-raster-threads=2']
