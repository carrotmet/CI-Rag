---
name: code-design-description
description: Web development project design guidelines and requirements. Use when Kimi needs to design or implement web projects with specific tech stack preferences (Python/FastAPI backend, SQLite database, JavaScript frontend, LazyLLM for RAG) and documentation requirements (design.md, api.md, database.md, changelog).
---

# 网页开发项目设计思路与要求

## 架构要求

在这个项目中，架构设计请有限遵循以下规范：

- 如果项目需要后端，优先使用python语言及相关成熟框架，对于API开发，优先使用Fastapi

- 如果项目需要数据库，优先使用sqlite

- 如果项目需要前端，优先使用js

- 如果用户需要RAG，务必使用Lazyallm框架，你可以参考以下网站获取LazyLLM的使用策略：

- 基础使用： [https://docs.lazyllm.ai/zh-cn/latest/Learn/learn/](https://docs.lazyllm.ai/zh-cn/latest/Learn/learn/)  

- 官方文档： [https://github.com/LazyAGI/LazyLLM](https://github.com/LazyAGI/LazyLLM) 

- 最佳实践： [https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/flow/) 

- 使用案例： [https://docs.lazyllm.ai/zh-cn/latest/Cookbook/](https://docs.lazyllm.ai/zh-cn/latest/Cookbook/) 

- API： [https://docs.lazyllm.ai/zh-cn/latest/API%20Reference/](https://docs.lazyllm.ai/zh-cn/latest/API%20Reference/cli/) 
- 长文档生成：[https://docs.lazyllm.ai/zh-cn/latest/Cookbook/great_writer/](https://docs.lazyllm.ai/zh-cn/latest/Cookbook/great_writer/)
- functioncall：[https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/functionCall/?h=react#react](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/functionCall/?h=react#react)
- 数据处理：[https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/data_process/](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/data_process/)
- pipeline：[https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/flow/?h=](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/flow/?h=)

- 示例代码：(./scrpts/02baseRAG.py) (./scrpts/03pipline.py)

- 如果项目没有docker文件，项目需要附带一份docker镜像打包文件，便于Linux服务器部署

## 设计思路

- 文档优先：需要将网站开发任务以文档形式拆分，同时交付代码与文档，并打包放置在新建的doc文件夹下。必要的文档及文档内容包括：

- 模块设计文档desgin.md： 设计思路 整体风格 主体模块（包含模块功能拆分说明）

- API接口设计文档api.md：Uml统一建模(类图 用例图 时序图) 接口名称 入参 出参

- 数据库建表文档database.md：ER图 表名 建表语句

- 更新日志文档log-更新日期-版本号.md：更新内容

- 脚本优先：如果遇到服务器启动 数据库连接等多步骤 重复性高 集成度高的要求，优先考虑将功能封装为CLI或用户操作系统支持的脚本进行处理

- 分块处理：如果遇到代码书写超过篇幅限制、上下文限制、token限制的情况。这说明项目模块设计不合理，需要将超出篇幅的独立模块进行更加精细化的拆分

## 设计风格

- 具有设计师思维