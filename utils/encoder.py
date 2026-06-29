BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def encode_base62(num: int) -> str:
    """Encodes a positive integer into a Base62 string."""
    if num < 0:
        raise ValueError("Only non-negative integers can be encoded.")
    if num == 0:
        return BASE62_ALPHABET[0]
    
    arr = []
    base = len(BASE62_ALPHABET)
    while num:
        num, rem = divmod(num, base)
        arr.append(BASE62_ALPHABET[rem])
    arr.reverse()
    return "".join(arr)

def decode_base62(string: str) -> int:
    """Decodes a Base62 string back into an integer."""
    base = len(BASE62_ALPHABET)
    num = 0
    for char in string:
        if char not in BASE62_ALPHABET:
            raise ValueError(f"Invalid character '{char}' in Base62 string.")
        num = num * base + BASE62_ALPHABET.index(char)
    return num

def generate_short_code(db_id: int) -> str:
    """
    Generates a 6-character short code from a database integer ID.
    Pads with the first character of the alphabet ('0') if the encoded string is less than 6 chars.
    """
    encoded = encode_base62(db_id)
    # Pad with the 0th character ('0') to ensure exactly 6 characters
    return encoded.zfill(6)
