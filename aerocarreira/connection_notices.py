"""Evita inundar o registro de voo enquanto o MSFS está fechado."""

class ReconnectWarningFilter:
    def __init__(self):
        self._logged=False

    def reset(self):
        self._logged=False

    def should_log(self,message):
        if not str(message).startswith('Conexão interrompida:'):
            return True
        if self._logged:
            return False
        self._logged=True
        return True
