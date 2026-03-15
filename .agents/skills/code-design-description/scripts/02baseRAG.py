import lazyllm
import os

print(os.getenv('LAZYLLM_KIMI_API_KEY'))
# 文档管理
documents=lazyllm.Document(dataset_path="D:/github.com/carrotmet/lazyllm/myvenvforllm/data_kb")

# 检索器
# join根据下游组件做选择
retriever=lazyllm.Retriever(doc=documents, group_name="CoarseChunk", similarity="bm25_chinese", topk=3, output_format='content', join='')
retriever.start()

# 生成器
# 提示词可选chat，alpaca
prompt=('你将扮演一个人工智能问答助手的角色，完成一项对话任务。在这个任务中，你需要根据给定的上下文以及问题，给出你的回答。')
llm=lazyllm.OnlineChatModule(source="kimi").prompt(lazyllm.ChatPrompter(instruction=prompt, extra_keys=['context_str']))

# 在线推理
query = input('请输入问题\n')
res=llm({"query":query, "context_str":retriever(query=query)})

print(f'With Rag Answer:{res}')

# 内置web界面
chat = lazyllm.OnlineChatModule()
lazyllm.WebModule(chat, port=23333).start().wait()

