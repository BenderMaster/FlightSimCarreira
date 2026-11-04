import argparse
import json
from pathlib import Path
from .neo_inspect import inspect_neofly, discover_neofly_databases


def main():
    parser=argparse.ArgumentParser(description="AeroCarreira Lab (carreira original MSFS2020)")
    parser.add_argument("--inspect-neofly",type=Path,help="Inspeciona common.db ou std.bin sem ler registros")
    parser.add_argument("--output",type=Path,default=Path("neofly_analise"),help="Diretório isolado do relatório")
    parser.add_argument("--find-neofly",action="store_true",help="Procura common.db e std.bin nas pastas usuais (somente leitura)")
    from . import __version__
    parser.add_argument('--version',action='version',version='FlightSimCarreira '+__version__)
    parser.add_argument('--webview-host',help=argparse.SUPPRESS)
    parser.add_argument('--verify-native-webview',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.verify_native_webview:
        from .webview_host import verify_native_runtime
        print(verify_native_runtime())
        return
    if args.webview_host:
        from .webview_host import main as host_main
        host_main(args.webview_host);return
    if args.find_neofly:
        print(json.dumps([str(path) for path in discover_neofly_databases()],ensure_ascii=False,indent=2))
    elif args.inspect_neofly:
        print(json.dumps(inspect_neofly(args.inspect_neofly,args.output),ensure_ascii=False,indent=2))
    else:
        from .app import Application
        Application().run()

if __name__=="__main__":main()
