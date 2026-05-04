import sqlite3
class BaseDB:
	def __init__(self):
		self.conn = None
		self.cursor = None
		self.path = None

	def add_to_db(self,*args, **kwargs):
		raise NotImplementedError("This method should be implemented by subclasses.")

	def delete_from_db(self,*args, **kwargs):
		raise NotImplementedError("This method should be implemented by subclasses.")
	
	def select_from_db(self,*args, **kwargs):
		raise NotImplementedError("This method should be implemented by subclasses.")
	
	def get_all_from_db(self,*args, **kwargs):
		raise NotImplementedError("This method should be implemented by subclasses.")
	
	def clear_db(self,*args, **kwargs):
		raise NotImplementedError("This method should be implemented by subclasses.")

