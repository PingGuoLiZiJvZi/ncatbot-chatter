from openai import OpenAI
import yaml
class BaseLLM:
	def __init__(self):
		self.messages = []
		with open("llm/prompt.yaml", "r", encoding="utf-8") as f:
			file = yaml.safe_load(f)
			self.messages.append({"role": "system", "content": file["prompt"]["base_prompt"]})
			self.messages.append({"role": "system", "content": file["prompt"]["character_prompt"]})
			
		with open("config.yaml", "r", encoding="utf-8") as f:
			file = yaml.safe_load(f)
			self.llm_api_key = file["api_key"]
			self.llm_base_url = file["base_url"]
			self.bot_uin = file["bot_uin"]
			self.messages.append({"role": "system", "content": f"注意,你本人的QQ号是{self.bot_uin}"})

	def generate_response(self,*args, **kwargs)->dict:
		raise NotImplementedError("This method should be implemented by subclasses.")
	
	def send_messages(self)->str:
		client = OpenAI(api_key=self.llm_api_key, base_url=self.llm_base_url)
		response = client.chat.completions.create(
        model = "deepseek-reasoner",
        messages = self.messages,
        stream = False,
        max_tokens = 2048,
        temperature = 1.3,
    )
		reply = response.choices[0].message.content
		return reply

class ResponseLLM(BaseLLM):
	def __init__(self):
		super().__init__()
		with open("llm/prompt.yaml", "r", encoding="utf-8") as f:
			self.messages.append({"role": "system", "content": yaml.safe_load(f)["prompt"]["response_prompt"]})

	def generate_response(self, *args, **kwargs):#收到的参数为dict->list->dict->list->dict
		s = str(args[0])
		self.messages.append({"role": "user", "content": f"私聊消息:{s}"})
		s = str(args[1])
		self.messages.append({"role": "user", "content": f"群聊消息:{s}"})
		reply = self.send_messages()
		return reply

class ConcentrateLLM(BaseLLM):
	def __init__(self):
		super().__init__()
		with open("llm/prompt.yaml", "r", encoding="utf-8") as f:
			self.messages.append({"role": "system", "content": yaml.safe_load(f)["prompt"]["concentrate_prompt"]})

	def generate_response(self, *args, **kwargs):
		s = str(args[0])
		self.messages.append({"role": "user", "content": s})
		s = str(args[1])
		self.messages.append({"role": "user", "content": f"你接下来收到的是已读记忆:{s}"})
		s = str(args[2])
		self.messages.append({"role": "user", "content": f"你接下来收到的是待存记忆:{s}"})
		s = str(args[3])
		self.messages.append({"role": "user", "content": f"你接下来收到的是长期记忆:{s}"})
		reply = self.send_messages()
		return reply

if __name__ == "__main__":
	llm = ResponseLLM()
	print(llm.generate_response({"test": "请随意回复,这是测试"}))  
	llm = ConcentrateLLM()
	print(llm.generate_response({"test": "请随意回复,这是测试"}, [{"test": "这是已读记忆"}], [{"test": "这是待存记忆"}], [{"test": "这是长期记忆"}]))
