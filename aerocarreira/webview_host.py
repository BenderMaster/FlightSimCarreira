"""Separate native WebView process; Tk/SimConnect remain on their owning thread."""
import json
import sys
import urllib.request

def main():
    import webview
    url=sys.argv[1];origin,token=url.split('/#',1)
    window=webview.create_window('FlightSimCarreira • Midnight Ops',url,width=1600,height=900,min_size=(800,480),background_color='#030e17')
    def closed():
        try:
            request=urllib.request.Request(origin+'/command',data=json.dumps({'action':'close'}).encode(),headers={'Origin':origin,'X-Flight-Token':token,'Content-Type':'application/json'})
            urllib.request.urlopen(request,timeout=3).close()
        except OSError:pass
    window.events.closed+=closed
    webview.start(gui='edgechromium' if sys.platform=='win32' else None,private_mode=True)
if __name__=='__main__':main()
