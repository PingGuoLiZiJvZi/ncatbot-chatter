#IndexDB类是一个记录群聊id/用户id(int),群聊名/用户名(str)的数据库类
#目前,只需实现添加和全获取功能即可
from BaseDB import BaseDB
import sqlite3

class IndexDB(BaseDB):
	def __init__(self, path):
		super().__init__()
		self.path = path
		self.conn = sqlite3.connect(self.path)
		self.cursor = self.conn.cursor()
		self.cursor.execute('''CREATE TABLE IF NOT EXISTS index_table (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL
		)''')
		self.conn.commit()

	def add_to_db(self, id, name):
		self.cursor.execute('INSERT INTO index_table (id, name) VALUES (?, ?)', (id, name))
		self.conn.commit()

	def get_all_from_db(self):
		self.cursor.execute('SELECT * FROM index_table')
		return self.cursor.fetchall()
	
	def select_from_db(self, *args, **kwargs):
		#提供一个查找功能。id查找
		if len(args) == 1:
			self.cursor.execute('SELECT * FROM index_table WHERE id = ?', (args[0],))
			return self.cursor.fetchone()
		else:
			raise ValueError("Invalid number of arguments. Expected 1 argument for id lookup.")
	
if __name__ == "__main__":
	index_db = IndexDB('index.db')
	index_db.add_to_db(1, 'Test Group')
	print(index_db.get_all_from_db())
	index_db.add_to_db(2, 'Test User')
	print(index_db.get_all_from_db())
	index_db.add_to_db(3, 'Another Group')
	print(index_db.get_all_from_db())
	print(index_db.select_from_db(1))  # 查找id为1的记录
	print(index_db.select_from_db(2))  # 查找id为2的记录
	print(index_db.select_from_db(3))  # 查找id为3的记录
	print(index_db.select_from_db(4))  # 查找id为4的记录，
	index_db.conn.close()