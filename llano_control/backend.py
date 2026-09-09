class UnsupportedProtocol(RuntimeError):
    pass

class HardwareBackend:
    capabilities = frozenset()
    def apply(self, profile):
        raise UnsupportedProtocol("Protocolo sin verificar: no se ha enviado ningún comando USB/HID")
