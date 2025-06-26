# Chatter 插件

**Chatter** 是一个用于 **Ncatbot** 的插件，提供了群聊消息和私聊消息的自动回复功能。

---

## ✨ 功能

1. Chatter 是一个支持单角色设定的 qq 聊天机器人插件
2. 支持多群聊，多私聊之间的记忆联动
3. 支持双层记忆，即短期内存记忆和长期数据库记忆(sqlite3实现)

---

## 🌟 特性

1. 采用主动模式设计，bot每隔一段时间即可主动扫描记忆库，检查是否需要主动发言
2. bot可以同时在多个群聊和私聊之间发送消息，并能关联其中的信息

---

## ⚙️ 配置
1. python版本为3.12.9
2. 在项目根目录下，运行以下命令进行依赖下载：
```bash
pip install -r requirements.txt
```
3. 按照要求，修改根目录下的 config.yaml.template 中的所有键的对应值，将文件重命名为 config.yaml
4. 因为群聊名称无法从消息中获取，对于你希望能标记群名称的群聊，请修改 db 目录下 group_name.yaml.template，添加对应 群聊id: 群聊名 的键值对，并将文件重命名为 group_name.yaml ,对于未标记的群聊，群聊名将会被标识为未知群名
5. 请在llm/character.yaml.template 中的 character_prompt: 后添加自己的角色设定与背景信息,随后将文件重命名为 character.yaml

---

## 🚀 使用

1. 使用
```bash
python main.py
```
2. 运行 bot，并在 bot 启动之后使用 root 账号发送一条 启动 消息以启动bot的主动循环