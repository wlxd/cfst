import base64
import pyaes
import requests
import re
UID = 3747000103274291200
UUID = "D32A04F8-40D2-42E8-AEC8-61FF7C705812"
AES_IV = b'VXH2THdPBsHEp+TY'
AES_KEY = b'VXH2THdPBsHEp+TY'
API_KEY = "G8Jxb2YtcONGmQwN7b5odg=="
def decrypt_aes_cbc(encrypted_text, key, iv):
    encrypted_text += '=' * (-len(encrypted_text) % 4)
    encrypted_bytes = base64.b64decode(encrypted_text)
    aes = pyaes.AESModeOfOperationCBC(key, iv=iv)
    decrypted = b"".join(aes.decrypt(encrypted_bytes[i:i+16]) for i in range(0, len(encrypted_bytes), 16))
    return decrypted[:-decrypted[-1]].decode('utf-8')
def fetch_data():
    url = "https://api.lytest.tk/v2/node/list/op"
    headers = {'Content-Type': 'application/json', 'User-Agent': 'International/3.3.37 (iPhone; iOS 16.5; Scale/3.00)'}
    body = {"d": "0", "key": API_KEY, "uid": UID, "vercode": "1", "uuid": UUID}
    response = requests.post(url, headers=headers, json=body)
    return response.json() if response.status_code == 200 else None
def generate_trojan_link(uid, server, tag):
    return f"trojan://{uid}@{server}:443#{tag}"
def normalize_name(name):
    name = re.sub(r'(\d+)', lambda x: x.group(1).zfill(2), name)
    name = re.sub(r'\s+', ' ', name)
    return name
def main():
    data = fetch_data()
    nodes = []
    if data:
        for item in data.get('data', []):
            enc_host, name, port = item.get('n'), item.get('b'), item.get('m')
            if enc_host and name and port:
                try:
                    host = decrypt_aes_cbc(enc_host, AES_KEY, AES_IV)
                    normalized_name = normalize_name(name)
                    trojan_link = generate_trojan_link(UID, host, normalized_name)
                    nodes.append((normalized_name, trojan_link))
                except Exception:
                    pass
    nodes.sort(key=lambda x: x[0])
    hyy = [link for _, link in nodes]
    for link in hyy:
        print(link)
if __name__ == "__main__":
    main()