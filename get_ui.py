import subprocess, xml.etree.ElementTree as ET
adb = 'adb'
subprocess.run([adb, 'shell', 'uiautomator', 'dump', '/sdcard/ui.xml'], capture_output=True)
subprocess.run([adb, 'pull', '/sdcard/ui.xml', 'ui.xml'], capture_output=True)
ns = 'http://schemas.android.com/apk/res/android'
root = ET.parse('ui.xml').getroot()
for n in root.iter():
    tx = (n.get(f'{{{ns}}}text') or '').strip()
    bd = n.get(f'{{{ns}}}bounds') or ''
    cls = n.get('class') or ''
    pkg = n.get(f'{{{ns}}}package') or ''
    rid = n.get('resource-id') or ''
    if tx and len(tx) > 1:
        print(f'text={tx!r} cls={cls} bounds={bd} pkg={pkg} rid={rid}')
print("Done")
