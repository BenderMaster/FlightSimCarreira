"""Separate native WebView process; Tk/SimConnect remain on their owning thread."""
import json
import sys
import urllib.request

def verify_native_runtime():
    """Exercita exatamente o backend pythonnet/WinForms usado no executável Windows.

    Não abre navegador ou interface alternativa. Falha com código != 0 em caso
    de DLL do pythonnet incompatível, bloqueada ou ausente.
    """
    if sys.platform != 'win32':
        raise RuntimeError('Verificação WinForms disponível somente no Windows')
    import clr
    import System
    import webview
    from webview.platforms import winforms
    screens = webview.screens
    if not screens:
        raise RuntimeError('pywebview/WinForms não encontrou tela disponível')
    return f'Python.Runtime e WinForms carregados; telas={len(screens)}'


def main(url=None):
    import webview
    url=url or sys.argv[1];origin,token=url.split('/#',1)
    class WindowAPI:
        def minimize(self):window.minimize()
    screen=webview.screens[0]
    width=min(1600,max(800,screen.width-32));height=min(900,max(440,screen.height-80))
    window=webview.create_window('FlightSim • Midnight Ops',url,width=width,height=height,min_size=(800,440),background_color='#030e17',frameless=True,easy_drag=False,js_api=WindowAPI())
    def closed():
        try:
            request=urllib.request.Request(origin+'/command',data=json.dumps({'action':'close'}).encode(),headers={'Origin':origin,'X-Flight-Token':token,'Content-Type':'application/json'})
            urllib.request.urlopen(request,timeout=3).close()
        except OSError:pass
    window.events.closed+=closed
    webview.start(gui='edgechromium' if sys.platform=='win32' else None,private_mode=True)
if __name__=='__main__':main()
