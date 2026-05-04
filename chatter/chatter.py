from memory.memory import MemoryManager
from llm.LLM import ResponseLLM
from chatter import tts
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from ncatbot.utils import get_log
import yaml
import json
import time
import threading
import numpy as np
import os
class Chatter:
	def __init__(self):
		self.memory = MemoryManager()
		self.bot = BotClient()
		self._log = get_log()
		self.llm = ResponseLLM()
		self.is_character = False
		self.t = threading.Thread(target=self.mainloop)

		with open("config.yaml", "r", encoding="utf-8") as f:
			file = yaml.safe_load(f)
			self.bot_uin = file["bot_uin"]
			self.root = file["root_uin"]
			self.loop_interval = file["loop_interval"]
			self.min_send_interval = file["min_send_interval"]
			self.max_send_interval = file["max_send_interval"]
		
		@self.bot.group_event()
		async def on_group_message(msg: GroupMessage):
			self._log.info(msg)
			if(self.is_character):
				await self.memory.add_group_memory(msg)
			else:
				self.random_number(msg)
				self.random_picture(msg)
				self.ccb(msg)
				self.text_to_speech(msg)

		@self.bot.private_event()
		async def on_private_message(msg: PrivateMessage):
			self._log.info(msg)
			self.character_control(msg)
			if(self.is_character):
				await self.memory.add_private_memory(msg)
			else:
				pass
		
	def run(self):
		self.bot.run(bt_uin=self.bot_uin, root=self.root)
#-----------------------------------------------简单功能插件---------------------------------------------------------------------------------------------------------------------------------
#今日人品功能插件，当有人发送“今日人品”时，随机生成一个0-100的数字，回复"你今日的人品值为{数字}，请谨慎使用"。
	def random_number(self,msg:GroupMessage):
		if(msg.raw_message == "今日人品"):
			random_number = np.random.randint(0, 101)
			self.bot.api.post_group_msg_sync(msg.group_id, f"你今日的人品值为{random_number}", at=msg.user_id)
	
	def random_picture(self, msg:GroupMessage):# 随机发送一张图片
		#判断消息前五个字符是否为“随机图片 ”
		#随后解析出其后的目录名，在D:\军火库下查询是否有该目录名的文件夹
		#如果有，打开并随机发送一张图片
		#如果没有，做出提示
		if(msg.raw_message[:2] == "随机"):
			directory_name = msg.raw_message[2:]
			directory_path = os.path.join("D:\\军火库", directory_name)
			if os.path.exists(directory_path) and os.path.isdir(directory_path):
				files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
				if files:
					random_file = np.random.choice(files)
					file_path = os.path.join(directory_path, random_file)
					self.bot.api.post_group_msg_sync(msg.group_id,  image=file_path)
				else:
					self.bot.api.post_group_msg_sync(msg.group_id, "这东西没图")
			else:
				self.bot.api.post_group_msg_sync(msg.group_id, "没这东西")

	def ccb(self,msg:GroupMessage):
		if 'ccb' in msg.raw_message:
			#检查 at 键是否存在
			at_user_id = None
			for mess in msg.message:
				if(mess['type'] == 'at' and mess['data']['qq']!='all'):
					at_user_id = mess['data']['qq']
			if not at_user_id is None:
				random_number1 = np.random.randint(1, 81)
				random_number2 = np.random.randint(1, 81)
				self.bot.api.post_group_msg_sync(msg.group_id, f"{msg.sender.card}为你提供了ccb服务,持续了{random_number1}min,注入了{random_number2}ml生命精华", at=at_user_id)
		
	def text_to_speech(self, msg:GroupMessage):
		if 'tts:' == msg.raw_message[:4] :
			text = msg.raw_message.replace('tts:','')
			if text:
				speech_tensors = tts.send_request(text)
				for speech_tensor in speech_tensors:
					if speech_tensor is not None:
						filename = f"output_{msg.message_id}.wav"
						filename = os.path.abspath(filename)
						tts.save_as_wav(speech_tensor, filename)
						self.bot.api.post_group_file_sync(msg.group_id, record=filename)
						os.remove(filename)
					else:
						self.bot.api.post_group_msg_sync(msg.group_id, "生成语音失败")
			else:
				self.bot.api.post_group_msg_sync(msg.group_id, "请提供文本以生成语音")
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------			

	def character_control(self, msg:PrivateMessage):
		if(msg.user_id == int(self.root) and msg.raw_message == "启动角色扮演"):
			if not self.is_character:
				self._log.info("Bot is starting...")
				self.t.start()
				self.is_character = True
		elif(msg.user_id == int(self.root) and msg.raw_message == "停止角色扮演"):
			self._log.info("Bot is stopping...")
			self.is_character = False
			self.t.join()
			self._log.info("Bot has stopped.")

	def calculate_send_interval(self):
		a = self.min_send_interval
		b = self.max_send_interval
		mean = (a + b) / 2
		std_dev = (b - a) / 6
		random_number = np.random.normal(mean, std_dev)
		random_number = max(a, min(b, random_number))
		return random_number

	def mainloop(self):
		self._log.info("Bot is running...")
		while True:
			try:
				self.loop()
			except Exception as e:
				self._log.error(f"An error occurred: {e}")
			for memory in self.memory.private_memory:
				if(len(memory.unread_memory) > 0):
					continue
			for memory in self.memory.group_memory:
				if(len(memory.unread_memory) > 0):
					continue
				if not self.is_character:
					return
			time.sleep(self.loop_interval*60)

	def loop(self):
		try:
			private_memory = self.memory.get_all_private_memory()
			group_memory = self.memory.get_all_group_memory()
			response = self.llm.generate_response(private_memory, group_memory)
			actions = self.parse_response(response)
			for action in actions:
				if action["行动类型"] == "发送消息":
					self.send_message(action)

					if action["聊天类型"] == "私聊":
						for memory in self.memory.private_memory:
							print("开始尝试加入私聊记忆")
							memory.add_self_message(action)
					elif action["聊天类型"] == "群聊":
						for memory in self.memory.group_memory:
							print("开始尝试加入群聊记忆")
							memory.add_self_message(action)
					
					time.sleep(self.calculate_send_interval())

			for memory in self.memory.private_memory:
				memory.process_after_read()

			for memory in self.memory.group_memory:
				memory.process_after_read()

			
		except KeyError as e:
			print(f"KeyError: {e} in loop method. Response: {response}")


	def get_json_list(self, data: str) -> str:
		last_close_bracket_index = data.rfind(']')
		# 查找倒数第一个 '[' 的下标
		last_open_bracket_index = data.rfind('[')
		
		# 如果两个字符都存在，并且 '[' 在 ']' 的左边
		if last_close_bracket_index != -1 and last_open_bracket_index != -1 and last_open_bracket_index < last_close_bracket_index:
			# 切片出它们之间的部分
			return data[last_open_bracket_index :last_close_bracket_index+1]
		else:
			# 如果条件不满足，返回空字符串
			return "[]"

	def parse_response(self, response: str) -> dict:
		print(f"Received response: {response}")
		try:
			response = self.get_json_list(response)
			print(response)
			actions = json.loads(response)
			if isinstance(actions, list):
				return actions
			else:
				self._log.error("Response is not a list.")
				return []
		except json.JSONDecodeError as e:
			self._log.error(f"JSON decode error: {e}")
			return []

	def send_message(self, message: dict):
		print(f"Sending message: {message}")
		if message["聊天类型"] == "私聊":
			if message["引用某条消息"] == "无":
				result = self.bot.api.post_private_msg_sync(message["聊天id"], message["消息内容"])
			else:
				result = self.bot.api.post_private_msg_sync(message["聊天id"], message["消息内容"], reply=message["引用某条消息"])
			if result['retcode'] == 0:
				print("发送成功")
			else:
				print("发送失败")

		elif message["聊天类型"] == "群聊":
			if( message["引用某条消息"] == "无"):
				if message["@某人"] == "无":
					result = self.bot.api.post_group_msg_sync(message["聊天id"], message["消息内容"])
				else:
					result = self.bot.api.post_group_msg_sync(message["聊天id"], message["消息内容"],at=message["@某人"])
			else:
				# if message["@某人"] == "无":
				result = self.bot.api.post_group_msg_sync(message["聊天id"], message["消息内容"], reply=message["引用某条消息"])
				# else:
				# 	result = self.bot.api.post_group_msg_sync(message["聊天id"], message["消息内容"], reply=message["引用某条消息"], at=message["@某人"])
			if result['retcode'] == 0:
				print("发送成功")
			else:
				print("发送失败")
					
		else:
			self._log.error("Invalid chat type.")
			return
		
# [
# 	{
# 		"行动类型":"<发送消息>",
# 		"聊天类型":"<私聊/群聊>",
# 		"聊天id":"<私聊id/群聊id>",
# 		"消息内容":"<消息内容>",
# 		"@某人":"<@某人(若需要@,此处写某人的qq号,不需要,写无,私聊一定写无)>",
# 		"引用某条消息":"<引用某条消息(若引用,此处写消息id,不需要,写无)>"
# 	}
# ]