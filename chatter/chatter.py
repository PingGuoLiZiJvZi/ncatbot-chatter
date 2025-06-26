from memory.memory import MemoryManager
from llm.LLM import ResponseLLM
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from ncatbot.utils import get_log
import yaml
import json
import time
import threading
import numpy as np
class Chatter:
	def __init__(self):
		self.memory = MemoryManager()
		self.bot = BotClient()
		self._log = get_log()
		self.llm = ResponseLLM()

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

			await self.memory.add_group_memory(msg)

		@self.bot.private_event()
		async def on_private_message(msg: PrivateMessage):
			self._log.info(msg)
		
			if(msg.user_id == int(self.root) and msg.raw_message == "启动"):
				self._log.info("Bot is starting...")
				t = threading.Thread(target=self.mainloop, daemon=True)
				t.start()
			else:
				await self.memory.add_private_memory(msg)
		
	def run(self):
		self.bot.run(bt_uin=self.bot_uin, root=self.root)

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