#!/usr/bin/env python3
"""Add the MLBB Link PC connection center and version-aware release checks."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

VERSION = "0.11.0"
VERSION_CODE = 13

def once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one marker, got {n}")
    return text.replace(old, new, 1)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: enhance_pc_dashboard.py source/mlbb-link")
    root = Path(sys.argv[1])
    hp = root / "host/mlbb_link_host.py"
    host = hp.read_text(encoding="utf-8")
    host, n = re.subn(r"^HOST_VERSION\s*=\s*['\"][^'\"]+['\"]\s*$",
                      f'HOST_VERSION = "{VERSION}"', host, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("HOST_VERSION assignment not found")
    css = r"""
.connection-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 0;padding:8px;background:#0c1520;border:1px solid #2c4052;border-radius:16px}
.connection-tab{flex:1 1 125px;min-height:42px;border:1px solid #344a5d;border-radius:10px;background:#142332;color:#cbd8e3;font-weight:800;font-size:12px;cursor:pointer;padding:10px}
.connection-tab:hover{border-color:#e1bd6b;color:#fff}.connection-tab.active{background:linear-gradient(135deg,#f5d785,#c79c4a);border-color:#f2d891;color:#211b0e}
.connection-panel{display:none;margin-top:12px}.connection-panel.active{display:block}.connection-panel .card{padding:22px}.connection-panel h2{font-size:19px;margin:8px 0}.connection-panel p,.connection-panel li{font-size:13px;line-height:1.65;color:#c4d2de}.connection-panel ol{padding-left:22px}.connection-panel code{color:#ffdf91;overflow-wrap:anywhere}
.connection-panel .state-line{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:10px 0;padding:12px 14px;border-radius:12px;background:#0e1924;border:1px solid #2e4355}.connection-panel .state-value{font-size:13px;color:#e6f0f7;text-align:right}.connection-panel .hint-box{margin-top:12px;padding:12px 14px;border-left:3px solid var(--gold);background:#192735;border-radius:0 10px 10px 0;color:#ccd8e2;font-size:12px;line-height:1.6}.connection-panel .btn{margin-top:8px}.panel-columns{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:720px){.panel-columns{grid-template-columns:1fr}.connection-tab{flex-basis:42%}}
"""
    host = once(host, "</style>", css + "</style>", "CSS insertion")
    tabs = r'''<nav class="connection-tabs" role="tablist" aria-label="Connection setup">
<button class="connection-tab active" id="tab-overview" role="tab" aria-selected="true" aria-controls="panel-overview" onclick="showConnectionTab('overview')">Overview</button>
<button class="connection-tab" id="tab-wifi" role="tab" aria-selected="false" aria-controls="panel-wifi" onclick="showConnectionTab('wifi')">Wi-Fi</button>
<button class="connection-tab" id="tab-usb" role="tab" aria-selected="false" aria-controls="panel-usb" onclick="showConnectionTab('usb')">USB</button>
<button class="connection-tab" id="tab-bluetooth" role="tab" aria-selected="false" aria-controls="panel-bluetooth" onclick="showConnectionTab('bluetooth')">Bluetooth Beta</button>
<button class="connection-tab" id="tab-dual" role="tab" aria-selected="false" aria-controls="panel-dual" onclick="showConnectionTab('dual')">Dual Connection</button>
<button class="connection-tab" id="tab-updates" role="tab" aria-selected="false" aria-controls="panel-updates" onclick="showConnectionTab('updates')">Updates</button>
</nav>
<section class="connection-panel active" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview"><div class="card"><div class="section-label">CONNECTION CENTER</div><h2>Connection setup & diagnostics</h2><p>Choose a tab for setup and live diagnostics. Select the actual transport in <b>MLBB Link Controller on your phone</b>; these PC tabs report readiness and do not remotely switch the phone's mode.</p><div class="panel-columns"><div class="state-line"><span>USB / TCP</span><strong class="state-value" id="usbStatusTab">Checking…</strong></div><div class="state-line"><span>Bluetooth SPP</span><strong class="state-value" id="btStatusTab">Checking…</strong></div></div><div class="hint-box">Recommended: start with Wi-Fi, verify USB by itself, then try DUAL. Bluetooth is experimental. Test in Practice Mode before a real match.</div></div></section>
<section class="connection-panel" id="panel-wifi" role="tabpanel" aria-labelledby="tab-wifi"><div class="card"><div class="section-label">WIRELESS · UDP</div><h2>Wi-Fi connection</h2><div class="state-line"><span>PC LAN IPv4</span><strong class="state-value" id="wifiHostIp">Detecting…</strong></div><div class="state-line"><span>Phone → PC port</span><strong class="state-value">UDP <span id="wifiPhonePort">28741</span></strong></div><ol><li>Connect the phone and PC to the same trusted Wi-Fi/LAN.</li><li>Copy this PC address into the phone controller's PC IP field.</li><li>Tap LINK and wait for CONNECTED.</li><li>Send a test input; the packet count above should increase.</li></ol><button class="btn secondary" onclick="copyWifiIp(this)">COPY PC IP</button><div class="hint-box">If the IP is missing, run the host directly on Bazzite rather than inside Distrobox/Toolbx. Guest Wi-Fi/client isolation can block device-to-device traffic.</div></div></section>
<section class="connection-panel" id="panel-usb" role="tabpanel" aria-labelledby="tab-usb"><div class="card"><div class="section-label">WIRED · ADB REVERSE + TCP</div><h2>USB connection</h2><div class="state-line"><span>Live USB status</span><strong class="state-value" id="usbStatusDetail">Checking…</strong></div><ol><li>Enable Developer options → USB debugging on Android.</li><li>Use a USB data cable and accept the RSA authorization prompt.</li><li>Run <code>adb devices</code>; the phone should show <code>device</code>, not <code>unauthorized</code>.</li><li>Choose USB in the phone controller. The host retries ADB reverse while running.</li></ol><button class="btn secondary" onclick="copyText('adb devices\nadb reverse tcp:28744 tcp:28744',this)">COPY ADB CHECK COMMANDS</button><div class="hint-box">If status stays waiting, install Android platform-tools, reauthorize the phone, and check <code>adb devices</code>. Keep Wi-Fi configured for DUAL.</div></div></section>
<section class="connection-panel" id="panel-bluetooth" role="tabpanel" aria-labelledby="tab-bluetooth"><div class="card"><div class="section-label">RFCOMM / SERIAL PORT PROFILE</div><h2>Bluetooth Beta</h2><div class="state-line"><span>Live Bluetooth status</span><strong class="state-value" id="btStatusDetail">Checking…</strong></div><ol><li>Pair the PC and phone in system Bluetooth settings first.</li><li>Ensure BlueZ, RFCOMM support and <code>sdptool</code> are installed.</li><li>Start the host, then select BT BETA in the phone controller.</li><li>Send test inputs and verify the host packet counter.</li></ol><button class="btn secondary" onclick="copyText('bluetoothctl power on\nbluetoothctl agent on\nbluetoothctl default-agent\nbluetoothctl scan on',this)">COPY BLUETOOTH SETUP COMMANDS</button><div class="hint-box">Bluetooth is experimental; pairing alone does not prove the control stream works. Prefer Wi-Fi, USB or DUAL until it passes device testing.</div></div></section>
<section class="connection-panel" id="panel-dual" role="tabpanel" aria-labelledby="tab-dual"><div class="card"><div class="section-label">USB PREFERRED · WI-FI BACKUP</div><h2>Dual Connection</h2><div class="panel-columns"><div class="state-line"><span>USB / TCP status</span><strong class="state-value" id="dualUsbStatus">Checking…</strong></div><div class="state-line"><span>Wi-Fi address</span><strong class="state-value" id="dualWifiIp">Detecting…</strong></div></div><ol><li>First verify Wi-Fi alone works and save the PC IP in the phone app.</li><li>Connect/authorize USB and wait for ADB reverse ready.</li><li>Choose DUAL on the phone controller. USB/TCP is preferred; Wi-Fi/UDP is used when the USB send fails.</li><li>In Practice Mode, test cable removal during joystick movement and check whether input resumes.</li></ol><div class="hint-box"><b>Important:</b> Failover depends on the phone sender detecting a failed transport; a short input gap may occur. This dashboard cannot guarantee zero missed inputs. Do not first-test it in a ranked match.</div></div></section>
<section class="connection-panel" id="panel-updates" role="tabpanel" aria-labelledby="tab-updates"><div class="card"><div class="section-label">RELEASE STATUS</div><h2>MLBB Link updates</h2><div class="state-line"><span>PC host version</span><strong class="state-value">v''' + VERSION + r'''</strong></div><div class="state-line"><span>Controller / bridge baseline</span><strong class="state-value">v''' + VERSION + r''' (code ''' + str(VERSION_CODE) + r''')</strong></div><p>The PC checks the public release manifest. Android requires the user to approve APK installation. The PC host is a Python script: download the newer file, stop the running host, replace the script, then restart it.</p><div class="actions"><a class="btn secondary" id="hostDownloadLink" href="https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/mlbb-link-beta/mlbb_link_host.py" target="_blank" rel="noopener">DOWNLOAD PC HOST</a><a class="btn secondary" href="https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/tag/mlbb-link-beta" target="_blank" rel="noopener">OPEN LATEST RELEASE</a></div><div class="hint-box">Keep the Android application ID and signing key stable for in-place APK updates. Never publish the signing keystore or its passwords.</div></div></section>
'''
    host = once(host, '<section class="grid">', tabs + '<section class="grid">', "connection tab insertion")
    status = "document.getElementById('btStatus').textContent=d.bluetooth_status||'Not ready';"
    extra = status + "document.getElementById('usbStatusTab').textContent=d.usb_status||'Not ready';document.getElementById('usbStatusDetail').textContent=d.usb_status||'Not ready';document.getElementById('dualUsbStatus').textContent=d.usb_status||'Not ready';document.getElementById('btStatusTab').textContent=d.bluetooth_status||'Not ready';document.getElementById('btStatusDetail').textContent=d.bluetooth_status||'Not ready';document.getElementById('wifiHostIp').textContent=(!d.host_ip||d.host_ip==='not detected')?'LAN IP NOT DETECTED':d.host_ip;document.getElementById('dualWifiIp').textContent=(!d.host_ip||d.host_ip==='not detected')?'LAN IP NOT DETECTED':d.host_ip;document.getElementById('wifiPhonePort').textContent=d.phone_port||28741;"
    host = once(host, status, extra, "connection status mirroring")
    start = host.find("async function checkUpdate(){")
    end = host.find("\nrefreshNow();", start)
    if start < 0 or end < 0:
        raise SystemExit("Existing update check function not found")
    update_js = '''function compareVersions(a,b){const aa=String(a||'0').split('.').map(v=>parseInt(v,10)||0),bb=String(b||'0').split('.').map(v=>parseInt(v,10)||0);for(let i=0;i<Math.max(aa.length,bb.length);i++){const x=aa[i]||0,y=bb[i]||0;if(x!==y)return x>y?1:-1;}return 0;}
function showConnectionTab(name){document.querySelectorAll('.connection-tab').forEach(el=>{const active=el.id==='tab-'+name;el.classList.toggle('active',active);el.setAttribute('aria-selected',active?'true':'false');});document.querySelectorAll('.connection-panel').forEach(el=>el.classList.toggle('active',el.id==='panel-'+name));}
async function copyText(value,button){const original=button.textContent;try{await navigator.clipboard.writeText(value);}catch(e){const el=document.createElement('textarea');el.value=value;document.body.appendChild(el);el.select();document.execCommand('copy');el.remove();}button.textContent='COPIED ✓';setTimeout(()=>button.textContent=original,1500);}
async function copyWifiIp(button){const ip=document.getElementById('wifiHostIp').textContent;if(!ip||ip==='LAN IP NOT DETECTED'||ip==='Detecting…'){button.textContent='IP NOT READY';setTimeout(()=>button.textContent='COPY PC IP',1400);return;}await copyText(ip,button);}
async function checkUpdate(){try{const r=await fetch('https://raw.githubusercontent.com/AndrewHorrison/mlbb-link-cloud-build/main/updates/latest.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)return;const d=await r.json();const currentCode=13;const currentHost='0.11.0';const appBanner=document.getElementById('updateBanner');if(Number(d.versionCode||0)>currentCode){appBanner.style.display='block';document.getElementById('updateText').textContent='Controller/bridge v'+d.versionName+' is newer than this PC bundle. Open the latest release and install the APKs.';}else{appBanner.style.display='none';}const hostBanner=document.getElementById('hostUpdateBanner');if(d.hostVersion&&compareVersions(d.hostVersion,currentHost)>0){hostBanner.style.display='block';document.getElementById('hostUpdateText').textContent='PC host v'+d.hostVersion+' is available.';if(d.hostScriptUrl){document.getElementById('hostDownloadLink').href=d.hostScriptUrl;document.getElementById('hostBannerDownload').href=d.hostScriptUrl;}}else{hostBanner.style.display='none';}}catch(e){}}
'''
    host = host[:start] + update_js + host[end:]
    host = once(host, '</div>\n<nav class="connection-tabs"',
                '</div><div id="hostUpdateBanner" style="display:none;margin-top:10px;background:#263c32;border:1px solid #66c99a;border-radius:12px;padding:14px;color:#e8fff3"><span id="hostUpdateText">PC host update available.</span> · <a id="hostBannerDownload" style="color:#ffe29a;font-weight:800" href="https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/mlbb-link-beta/mlbb_link_host.py" target="_blank" rel="noopener">DOWNLOAD PC HOST</a> (restart required)</div>\n<nav class="connection-tabs"', "PC host update banner insertion")
    hp.write_text(host, encoding="utf-8")

    for p in (root / "phone-controller/app/build.gradle", root / "waydroid-touch-bridge/app/build.gradle"):
        gradle = p.read_text(encoding="utf-8")
        gradle, c1 = re.subn(r"versionCode\s+\d+", f"versionCode {VERSION_CODE}", gradle, count=1)
        gradle, c2 = re.subn(r"versionName\s+['\"][^'\"]+['\"]", f"versionName '{VERSION}'", gradle, count=1)
        if c1 != 1 or c2 != 1: raise SystemExit(f"Could not update version in {p}")
        p.write_text(gradle, encoding="utf-8")
    for marker in ("panel-wifi", "panel-usb", "panel-bluetooth", "panel-dual", "panel-updates", "hostUpdateBanner", "showConnectionTab"):
        if marker not in host: raise SystemExit("Missing dashboard feature " + marker)
    print(f"Dashboard tabs installed; components set to v{VERSION}, Android versionCode {VERSION_CODE}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
