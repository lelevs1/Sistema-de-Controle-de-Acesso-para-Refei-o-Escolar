import binascii
# from biomini import match_templates, TemplateType  # comente esta linha

def hex_to_template(hex_string: str) -> bytearray:
    try:
        return bytearray.fromhex(hex_string)
    except ValueError as e:
        raise ValueError(f"HEX inválido: {e}")

def comparar_templates(hex1: str, hex2: str, security_level: int = 4) -> bool:
    # SIMULAÇÃO: sempre retorna True para testes (substituir depois)
    # Se a string hex for muito curta, pode até comparar os primeiros bytes
    if len(hex1) > 10 and len(hex2) > 10:
        return hex1[:20] == hex2[:20]  # comparação simples (não biométrica)
    return False