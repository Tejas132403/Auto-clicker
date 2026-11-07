import subprocess, xml.etree.ElementTree as ET, sys

adb = 'adb'
subprocess.run([adb, 'shell', 'uiautomator', 'dump', '/sdcard/ui.xml'], capture_output=True)
subprocess.run([adb, 'pull', '/sdcard/ui.xml', 'ui.xml'], capture_output=True)

ns = 'http://schemas.android.com/apk/res/android'
try:
    t = ET.parse('ui.xml')
except Exception as e:
    print(f'Parse error: {e}')
    print(open('ui.xml').read()[:500] if __import__('os').path.exists('ui.xml') else 'no ui.xml')
    sys.exit(1)

r = t.getroot()
count = 0
for n in r.iter():
    tx = (n.get(f'{{{ns}}}text') or '').strip()
    bd = n.get(f'{{{ns}}}bounds') or ''
    cls = n.get('class') or ''
    pkg = n.get(f'{{{ns}}}package') or ''
    rid = n.get('resource-id') or ''
    if tx and len(tx) > 1:
        count += 1
        print(f'text={tx!r} cls={cls} bounds={bd} pkg={pkg} rid={rid}')
print(f'TOTAL: {count} text elements')
