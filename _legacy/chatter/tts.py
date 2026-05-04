#一共需要实现两个函数
#接收文本，向服务器发起tts请求，返回音频数据
#接收音频数据，保存为qq可以发送为语音消息的格式，返回文件路径
import socket
import numpy as np
import soundfile as sf
server_address = ('localhost', 12345)

def recv_all(sock, size):
    buf = b''
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise RuntimeError("连接断开，未接收到完整数据")
        buf += chunk
    return buf

def send_request(text):
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.connect(server_address)
		sock.sendall(text.encode('utf-8'))
		
		#首先确认，收到数据开头是"OK"
		response = sock.recv(2)
		if response != b"OK":
			print("未收到正确的响应")
			return
		print("已连接到服务器")
		speech_tensors = []
		while True:
			speech_size_data = sock.recv(4)
			if not speech_size_data:
				print("异常结束")
				break
			if(speech_size_data[0:3] == b"END"):
				print("接收完毕")
				break

			speech_size = int.from_bytes(speech_size_data, 'big')
			speech_data = recv_all(sock,speech_size)
			if not speech_data:
				print("未收到音频数据")
				break
			speech_tensors.append(np.frombuffer(speech_data, dtype=np.float32).squeeze().astype(np.float32))
		return speech_tensors
		
def save_as_wav(speech_tensor, filename):
	sf.write(filename, speech_tensor, 24000)
	return filename

if __name__ == "__main__":
	text = "你好，这是一个测试。"
	speech_tensor = send_request(text)
	if speech_tensor is not None:
		save_as_wav(speech_tensor, "output.wav")
		print("音频已保存为output.wav")