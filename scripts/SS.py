import base64
import pyaes
import requests
import re
UID = 3747000103274291200
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
    url = "https://api.9527.click/v2/node/list"
    body = {"allNode": "1", "vercode": "1", "key": API_KEY, "uid": UID}
    response = requests.post(url, json=body)
    return response.json() if response.status_code == 200 else None
def generate_ss_link(server, ss_port, ss_pw, tag):
    return f"ss://aes-256-gcm:{ss_pw}@{server}:{ss_port}#{tag}"
def normalize_name(name):
    name = re.sub(r'(\d+)', lambda x: x.group(1).zfill(2), name)
    name = re.sub(r'\s+', ' ', name)
    return name
def main():
    data = fetch_data()
    nodes = []
    if data:
        for item in data.get('data', []):
            ip, name, ss_port, ss_pw = item.get('ip'), item.get('name'), item.get('ss_port'), item.get('ss_password')
            if ip and name and ss_port and ss_pw:
                try:
                    IP = decrypt_aes_cbc(ip, AES_KEY, AES_IV)
                    ss_pw = decrypt_aes_cbc(ss_pw, AES_KEY, AES_IV)
                    normalized_name = normalize_name(name)
                    ss_link = generate_ss_link(IP, ss_port, ss_pw, normalized_name)
                    nodes.append((normalized_name, ss_link))
                except Exception:
                    pass
    nodes.sort(key=lambda x: x[0])
    hyy = [link for _, link in nodes]
    for link in hyy:
        print(link)
if __name__ == "__main__":
    main()