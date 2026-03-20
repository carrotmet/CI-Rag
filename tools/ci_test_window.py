#!/usr/bin/env python3
"""
CI-RAG-ROUTER 测试窗口

简单的 GUI 工具用于测试和调试 CI 架构工作流程。
支持 Level 0/1/2 的渐进式测试。

Usage:
    python tools/ci_test_window.py
"""

import sys
import os
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import tkinter
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("Error: tkinter not available. Please install Python with tkinter support.")
    sys.exit(1)

# Import CI architecture
from ci_architecture.level0 import Level0Router, extract_features
from ci_architecture.level1 import Level1Router
from ci_architecture.level2 import Level2Router, PromptBuilder, build_level2_context

# Import V2 Orchestrator
try:
    from ci_architecture.orchestrator import SmartOrchestratorV2, OrchestratorGuide
    ORCHESTRATOR_V2_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_V2_AVAILABLE = False
    print("Warning: SmartOrchestratorV2 not available")


class CIRouterTestWindow:
    """CI-RAG-ROUTER 测试窗口主类"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CI-RAG-ROUTER 测试工具")
        self.root.geometry("1000x800")
        self.root.minsize(900, 700)
        
        # Initialize routers
        self.router = None
        self.level1_router = None
        self.level2_router = None
        self.documents = None
        self.orchestrator_v2 = None
        self.init_routers()
        
        # Build UI
        self.build_ui()
        
    def init_routers(self):
        """Initialize Level 0, Level 1 and Level 2 routers"""
        # Level 0
        try:
            self.router = Level0Router()
            self.router_status = self.router.get_status().value
        except Exception as e:
            self.router_status = f"Error: {e}"
        
        # Level 1 - load documents
        try:
            from data.medical_symptoms import get_medical_dataset
            self.documents = get_medical_dataset()
            self.level1_status = f"就绪 (文档数: {len(self.documents)})"
        except Exception as e:
            self.level1_status = f"未就绪: {e}"
            self.documents = None
        
        # Level 2 - check availability
        try:
            import os
            api_key = os.environ.get("CI_LLM_API_KEY")
            if api_key:
                self.level2_status = "就绪 (API Key 已配置)"
            else:
                self.level2_status = "未就绪: 未配置 API Key"
        except Exception as e:
            self.level2_status = f"未就绪: {e}"
        
        # V2 Orchestrator
        if ORCHESTRATOR_V2_AVAILABLE:
            try:
                self.orchestrator_v2 = SmartOrchestratorV2(
                    l0_router=self.router,
                    l1_router=None,  # Will be set when needed
                    l2_router=None   # Will be set when needed
                )
                self.orchestrator_v2_status = "就绪"
            except Exception as e:
                self.orchestrator_v2_status = f"未就绪: {e}"
        else:
            self.orchestrator_v2_status = "不可用"
            
    def build_ui(self):
        """Build the user interface"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)  # Result area expands
        
        # ===== Header Section =====
        header_frame = ttk.LabelFrame(main_frame, text="系统状态", padding="5")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        # Level 0 Status
        ttk.Label(header_frame, text="Level 0:").grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(header_frame, text=self.router_status, 
                                     font=('Arial', 10, 'bold'))
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 20))
        
        # Level 1 Status
        ttk.Label(header_frame, text="Level 1:").grid(row=0, column=2, sticky=tk.W)
        self.level1_status_label = ttk.Label(header_frame, text=self.level1_status,
                                             font=('Arial', 10))
        self.level1_status_label.grid(row=0, column=3, sticky=tk.W, padx=(5, 20))
        
        # Level 2 Status
        ttk.Label(header_frame, text="Level 2:").grid(row=0, column=4, sticky=tk.W)
        self.level2_status_label = ttk.Label(header_frame, text=self.level2_status,
                                             font=('Arial', 10))
        self.level2_status_label.grid(row=0, column=5, sticky=tk.W, padx=(5, 20))
        
        # Reload button
        ttk.Button(header_frame, text="重新加载模型", 
                  command=self.reload_routers).grid(row=0, column=6, padx=(10, 0))
        
        # ===== Mode Selection Section =====
        mode_frame = ttk.LabelFrame(main_frame, text="执行模式", padding="5")
        mode_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Mode selection variables
        self.use_level0_var = tk.BooleanVar(value=True)
        self.use_level1_var = tk.BooleanVar(value=False)
        self.use_level2_var = tk.BooleanVar(value=False)
        
        # Checkboxes for mode selection
        ttk.Checkbutton(mode_frame, text="启用 Level 0 (路由)", 
                       variable=self.use_level0_var,
                       command=self.on_mode_change).pack(side=tk.LEFT, padx=(10, 20))
        ttk.Checkbutton(mode_frame, text="启用 Level 1 (检索)", 
                       variable=self.use_level1_var,
                       command=self.on_mode_change).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Checkbutton(mode_frame, text="启用 Level 2 (LLM)", 
                       variable=self.use_level2_var,
                       command=self.on_mode_change).pack(side=tk.LEFT, padx=(0, 20))
        
        # Mode description label
        self.mode_desc_label = ttk.Label(mode_frame, text="当前: 仅 Level 0 路由", 
                                        foreground="blue", font=('Arial', 9, 'italic'))
        self.mode_desc_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # V2 Orchestrator checkbox
        self.use_v2_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(mode_frame, text="使用 V2 协调器 (带 Guide)", 
                       variable=self.use_v2_var,
                       command=self.on_mode_change).pack(side=tk.RIGHT, padx=(20, 10))
        
        # ===== Input Section =====
        input_frame = ttk.LabelFrame(main_frame, text="查询输入", padding="5")
        input_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # Query input
        self.query_text = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.query_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.query_text.insert("1.0", "输入查询语句，例如：患者咳嗽有铁锈色痰，胸痛发热")
        self.query_text.bind('<Return>', self.on_enter_pressed)
        
        # Buttons frame
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.execute_btn = ttk.Button(btn_frame, text="执行 (Enter)", 
                                     command=self.execute_routing)
        self.execute_btn.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="清空", 
                  command=self.clear_input).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="示例查询 ▼", 
                  command=self.show_examples).pack(side=tk.LEFT)
        
        # ===== Results Section =====
        result_frame = ttk.LabelFrame(main_frame, text="路由结果", padding="5")
        result_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Tab 1: Summary view
        self.summary_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.summary_frame, text="摘要")
        self.build_summary_tab()
        
        # Tab 2: Features view
        self.features_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.features_frame, text="特征详情")
        self.build_features_tab()
        
        # Tab 3: Level 1 Retrieval Results
        self.retrieval_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.retrieval_frame, text="检索结果 (L1)")
        self.build_retrieval_tab()
        
        # Tab 4: JSON view
        self.json_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.json_frame, text="原始数据")
        self.build_json_tab()
        
        # Tab 5: Level 2 Results
        self.level2_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.level2_frame, text="LLM 仲裁 (L2)")
        self.build_level2_tab()
        
        # Tab 6: Orchestrator V2
        self.orchestrator_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.orchestrator_frame, text="协调器 (V2)")
        self.build_orchestrator_tab()
        
        # Tab 7: History
        self.history_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.history_frame, text="历史记录")
        self.build_history_tab()
        
        # Status bar
        self.status_bar = ttk.Label(main_frame, text="就绪", relief=tk.SUNKEN)
        self.status_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Store history
        self.history = []
        
    def on_mode_change(self):
        """Handle mode selection change"""
        use_l0 = self.use_level0_var.get()
        use_l1 = self.use_level1_var.get()
        use_l2 = self.use_level2_var.get()
        use_v2 = self.use_v2_var.get()
        
        modes = []
        if use_l0:
            modes.append("L0")
        if use_l1:
            modes.append("L1")
        if use_l2:
            modes.append("L2")
        
        if use_v2:
            self.mode_desc_label.config(text="当前: V2 协调器模式 (Guide-based)", foreground="purple")
        elif not modes:
            self.mode_desc_label.config(text="当前: 请至少选择一个模式", foreground="blue")
        elif len(modes) == 1:
            mode_names = {"L0": "仅 Level 0 路由 (快速)",
                         "L1": "仅 Level 1 检索",
                         "L2": "仅 Level 2 LLM"}
            self.mode_desc_label.config(text=f"当前: {mode_names[modes[0]]}", foreground="blue")
        else:
            self.mode_desc_label.config(text=f"当前: {' + '.join(modes)} 完整流程", foreground="blue")
            
    def build_summary_tab(self):
        """Build the summary results tab"""
        # CI Assessment
        ci_frame = ttk.LabelFrame(self.summary_frame, text="CI 评估", padding="10")
        ci_frame.pack(fill=tk.X, pady=(0, 10))
        
        # C and I display
        row = 0
        ttk.Label(ci_frame, text="复杂度 (C):").grid(row=row, column=0, sticky=tk.W)
        self.c_label = ttk.Label(ci_frame, text="-", font=('Arial', 12, 'bold'))
        self.c_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 20))
        
        ttk.Label(ci_frame, text="信息充分性 (I):").grid(row=row, column=2, sticky=tk.W)
        self.i_label = ttk.Label(ci_frame, text="-", font=('Arial', 12, 'bold'))
        self.i_label.grid(row=row, column=3, sticky=tk.W, padx=(5, 0))
        
        # Zone
        row += 1
        ttk.Label(ci_frame, text="路由区域:").grid(row=row, column=0, sticky=tk.W, pady=(10, 0))
        self.zone_label = ttk.Label(ci_frame, text="-", font=('Arial', 16, 'bold'), foreground="blue")
        self.zone_label.grid(row=row, column=1, columnspan=3, sticky=tk.W, padx=(5, 0), pady=(10, 0))
        
        # Confidence
        conf_frame = ttk.LabelFrame(self.summary_frame, text="置信度", padding="10")
        conf_frame.pack(fill=tk.X, pady=(0, 10))
        
        row = 0
        ttk.Label(conf_frame, text="σ_c (复杂度置信度):").grid(row=row, column=0, sticky=tk.W)
        self.sigma_c_label = ttk.Label(conf_frame, text="-")
        self.sigma_c_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 0))
        self.sigma_c_bar = ttk.Progressbar(conf_frame, length=200, mode='determinate', maximum=100)
        self.sigma_c_bar.grid(row=row, column=2, padx=(10, 0))
        
        row += 1
        ttk.Label(conf_frame, text="σ_i (信息置信度):").grid(row=row, column=0, sticky=tk.W, pady=(5, 0))
        self.sigma_i_label = ttk.Label(conf_frame, text="-")
        self.sigma_i_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        self.sigma_i_bar = ttk.Progressbar(conf_frame, length=200, mode='determinate', maximum=100)
        self.sigma_i_bar.grid(row=row, column=2, padx=(10, 0), pady=(5, 0))
        
        row += 1
        ttk.Label(conf_frame, text="σ_joint (联合置信度):").grid(row=row, column=0, sticky=tk.W, pady=(5, 0))
        self.sigma_joint_label = ttk.Label(conf_frame, text="-", font=('Arial', 10, 'bold'))
        self.sigma_joint_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        self.sigma_joint_bar = ttk.Progressbar(conf_frame, length=200, mode='determinate', maximum=100)
        self.sigma_joint_bar.grid(row=row, column=2, padx=(10, 0), pady=(5, 0))
        
        # Level 1 specific results
        self.l1_frame = ttk.LabelFrame(self.summary_frame, text="Level 1 检索结果", padding="10")
        self.l1_frame.pack(fill=tk.X, pady=(0, 10))
        
        row = 0
        ttk.Label(self.l1_frame, text="融合后 I_mean:").grid(row=row, column=0, sticky=tk.W)
        self.i_mean_label = ttk.Label(self.l1_frame, text="-", font=('Arial', 10, 'bold'))
        self.i_mean_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 20))
        
        ttk.Label(self.l1_frame, text="融合后 σ_I:").grid(row=row, column=2, sticky=tk.W)
        self.sigma_i_fused_label = ttk.Label(self.l1_frame, text="-")
        self.sigma_i_fused_label.grid(row=row, column=3, sticky=tk.W, padx=(5, 0))
        
        row += 1
        ttk.Label(self.l1_frame, text="冲突检测:").grid(row=row, column=0, sticky=tk.W, pady=(5, 0))
        self.conflict_label = ttk.Label(self.l1_frame, text="-")
        self.conflict_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
        ttk.Label(self.l1_frame, text="数据源:").grid(row=row, column=2, sticky=tk.W, pady=(5, 0))
        self.sources_label = ttk.Label(self.l1_frame, text="-")
        self.sources_label.grid(row=row, column=3, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
        # Source reliabilities
        row += 1
        ttk.Label(self.l1_frame, text="源可靠性:").grid(row=row, column=0, sticky=tk.W, pady=(5, 0))
        self.reliability_label = ttk.Label(self.l1_frame, text="-", font=('Consolas', 9))
        self.reliability_label.grid(row=row, column=1, columnspan=3, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
        # Decision
        decision_frame = ttk.LabelFrame(self.summary_frame, text="决策", padding="10")
        decision_frame.pack(fill=tk.X, pady=(0, 10))
        
        row = 0
        ttk.Label(decision_frame, text="处理方式:").grid(row=row, column=0, sticky=tk.W)
        self.decision_label = ttk.Label(decision_frame, text="-", font=('Arial', 10, 'bold'))
        self.decision_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 0))
        
        row += 1
        ttk.Label(decision_frame, text="路由模式:").grid(row=row, column=0, sticky=tk.W, pady=(5, 0))
        self.mode_label = ttk.Label(decision_frame, text="-")
        self.mode_label.grid(row=row, column=1, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
        # Timing
        timing_frame = ttk.LabelFrame(self.summary_frame, text="性能", padding="10")
        timing_frame.pack(fill=tk.X)
        
        ttk.Label(timing_frame, text="处理耗时:").grid(row=0, column=0, sticky=tk.W)
        self.time_label = ttk.Label(timing_frame, text="-")
        self.time_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
    def build_features_tab(self):
        """Build the features detail tab"""
        # Feature descriptions
        self.feature_names = [
            ("len_char", "字符长度", "查询字符串的总字符数"),
            ("len_word", "词数", "按空格分割的词数"),
            ("char_entropy", "字符熵", "字符级香农熵，检测随机性"),
            ("word_entropy", "词熵", "词级香农熵，检测词汇多样性"),
            ("domain_switch_cnt", "领域切换", "跨领域关键词切换次数"),
            ("has_question", "疑问句", "是否包含疑问词或问号"),
            ("digit_ratio", "数字比例", "数字字符占总字符比例"),
            ("user_freq", "用户频率", "用户历史查询频率（预留）"),
            ("avg_complexity", "平均复杂度", "用户历史平均复杂度（预留）"),
            ("success_rate", "成功率", "用户历史成功率（预留）"),
            ("reserved_10", "预留", "预留特征"),
            ("reserved_11", "预留", "预留特征"),
        ]
        
        # Create treeview
        columns = ('index', 'name', 'value', 'description')
        self.feature_tree = ttk.Treeview(self.features_frame, columns=columns, show='headings')
        
        self.feature_tree.heading('index', text='#')
        self.feature_tree.heading('name', text='特征名')
        self.feature_tree.heading('value', text='值')
        self.feature_tree.heading('description', text='说明')
        
        self.feature_tree.column('index', width=30, anchor='center')
        self.feature_tree.column('name', width=150)
        self.feature_tree.column('value', width=100)
        self.feature_tree.column('description', width=400)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.features_frame, orient=tk.VERTICAL, command=self.feature_tree.yview)
        self.feature_tree.configure(yscrollcommand=scrollbar.set)
        
        self.feature_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initialize with empty rows
        for i, (name, cn_name, desc) in enumerate(self.feature_names):
            self.feature_tree.insert('', 'end', values=(i, f"{name}\n{cn_name}", '-', desc))
            
    def build_retrieval_tab(self):
        """Build the Level 1 retrieval results tab"""
        # Create notebook for retrieval sub-tabs
        retrieval_notebook = ttk.Notebook(self.retrieval_frame)
        retrieval_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Sub-tab 1: Overview
        overview_frame = ttk.Frame(retrieval_notebook, padding="10")
        retrieval_notebook.add(overview_frame, text="融合概览")
        
        self.retrieval_text = scrolledtext.ScrolledText(overview_frame, wrap=tk.WORD, 
                                                        font=('Consolas', 10))
        self.retrieval_text.pack(fill=tk.BOTH, expand=True)
        self.retrieval_text.insert("1.0", "启用 Level 1 后将显示检索融合结果")
        
        # Sub-tab 2: Vector Results
        vector_frame = ttk.Frame(retrieval_notebook, padding="10")
        retrieval_notebook.add(vector_frame, text="向量检索")
        
        self.vector_text = scrolledtext.ScrolledText(vector_frame, wrap=tk.WORD,
                                                     font=('Consolas', 10))
        self.vector_text.pack(fill=tk.BOTH, expand=True)
        self.vector_text.insert("1.0", "启用 Level 1 后将显示向量检索结果")
        
        # Sub-tab 3: Keyword Results
        keyword_frame = ttk.Frame(retrieval_notebook, padding="10")
        retrieval_notebook.add(keyword_frame, text="关键词检索")
        
        self.keyword_text = scrolledtext.ScrolledText(keyword_frame, wrap=tk.WORD,
                                                      font=('Consolas', 10))
        self.keyword_text.pack(fill=tk.BOTH, expand=True)
        self.keyword_text.insert("1.0", "启用 Level 1 后将显示关键词检索结果")
        
        # Sub-tab 4: Top Documents
        docs_frame = ttk.Frame(retrieval_notebook, padding="10")
        retrieval_notebook.add(docs_frame, text="Top 文档")
        
        columns = ('rank', 'source', 'score', 'content')
        self.docs_tree = ttk.Treeview(docs_frame, columns=columns, show='headings', height=15)
        
        self.docs_tree.heading('rank', text='#')
        self.docs_tree.heading('source', text='来源')
        self.docs_tree.heading('score', text='分数')
        self.docs_tree.heading('content', text='内容')
        
        self.docs_tree.column('rank', width=30, anchor='center')
        self.docs_tree.column('source', width=80, anchor='center')
        self.docs_tree.column('score', width=80)
        self.docs_tree.column('content', width=600)
        
        scrollbar = ttk.Scrollbar(docs_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        self.docs_tree.configure(yscrollcommand=scrollbar.set)
        
        self.docs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
    def build_level2_tab(self):
        """Build the Level 2 LLM arbitration tab"""
        # Create notebook for Level 2 sub-tabs
        level2_notebook = ttk.Notebook(self.level2_frame)
        level2_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Sub-tab 1: LLM Result
        result_frame = ttk.Frame(level2_notebook, padding="10")
        level2_notebook.add(result_frame, text="LLM 仲裁结果")
        
        self.level2_result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD,
                                                            font=('Consolas', 10))
        self.level2_result_text.pack(fill=tk.BOTH, expand=True)
        self.level2_result_text.insert("1.0", "启用 Level 2 后将显示 LLM 仲裁结果")
        
        # Sub-tab 2: LLM Reasoning
        reasoning_frame = ttk.Frame(level2_notebook, padding="10")
        level2_notebook.add(reasoning_frame, text="推理过程")
        
        self.level2_reasoning_text = scrolledtext.ScrolledText(reasoning_frame, wrap=tk.WORD,
                                                               font=('Consolas', 10))
        self.level2_reasoning_text.pack(fill=tk.BOTH, expand=True)
        self.level2_reasoning_text.insert("1.0", "启用 Level 2 后将显示 LLM 推理过程")
        
        # Sub-tab 3: Prompt Construction
        prompt_frame = ttk.Frame(level2_notebook, padding="10")
        level2_notebook.add(prompt_frame, text="提示词构建")
        
        self.level2_prompt_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD,
                                                            font=('Consolas', 9))
        self.level2_prompt_text.pack(fill=tk.BOTH, expand=True)
        self.level2_prompt_text.insert("1.0", "启用 Level 2 后将显示构建的提示词和调用参数")
        
        # Sub-tab 4: Metrics
        metrics_frame = ttk.Frame(level2_notebook, padding="10")
        level2_notebook.add(metrics_frame, text="成本与延迟")
        
        self.level2_metrics_text = scrolledtext.ScrolledText(metrics_frame, wrap=tk.WORD,
                                                             font=('Consolas', 10))
        self.level2_metrics_text.pack(fill=tk.BOTH, expand=True)
        self.level2_metrics_text.insert("1.0", "启用 Level 2 后将显示成本和延迟指标")
        
    def build_json_tab(self):
        """Build the raw JSON tab"""
        self.json_text = scrolledtext.ScrolledText(self.json_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.json_text.pack(fill=tk.BOTH, expand=True)
        self.json_text.insert("1.0", "执行查询后将显示原始 JSON 数据")
        
    def build_history_tab(self):
        """Build the history tab"""
        # History list
        columns = ('time', 'query', 'zone', 'mode', 'escalate')
        self.history_tree = ttk.Treeview(self.history_frame, columns=columns, show='headings')
        
        self.history_tree.heading('time', text='时间')
        self.history_tree.heading('query', text='查询')
        self.history_tree.heading('zone', text='区域')
        self.history_tree.heading('mode', text='模式')
        self.history_tree.heading('escalate', text='升级')
        
        self.history_tree.column('time', width=60)
        self.history_tree.column('query', width=350)
        self.history_tree.column('zone', width=50, anchor='center')
        self.history_tree.column('mode', width=120)
        self.history_tree.column('escalate', width=50, anchor='center')
        
        scrollbar = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Clear history button
        ttk.Button(self.history_frame, text="清空历史", 
                  command=self.clear_history).pack(side=tk.BOTTOM, pady=(5, 0))
        
    def on_enter_pressed(self, event):
        """Handle Enter key press"""
        # Check if Shift is pressed for multi-line
        if not event.state & 0x1:  # Shift not pressed
            self.execute_routing()
            return 'break'  # Prevent default newline
        
    def execute_routing(self):
        """Execute the routing process based on selected mode"""
        query = self.query_text.get("1.0", tk.END).strip()
        
        if not query:
            messagebox.showwarning("输入为空", "请输入查询语句")
            return
        
        # Check if V2 orchestrator is enabled
        if self.use_v2_var.get():
            self.execute_orchestrator_v2()
            return
        
        use_l0 = self.use_level0_var.get()
        use_l1 = self.use_level1_var.get()
        use_l2 = self.use_level2_var.get()
        
        if not use_l0 and not use_l1 and not use_l2:
            messagebox.showwarning("模式错误", "请至少选择一种执行模式")
            return
            
        self.status_bar.config(text=f"正在处理: {query[:50]}...")
        self.root.update()
        
        try:
            # Measure time
            start_time = time.time()
            
            result = {}
            l0_result = None
            l1_result = None
            l2_result = None
            
            # Level 0
            if use_l0:
                l0_result = self.router.route(query)
                result['level0'] = l0_result
            
            # Level 1
            if use_l1:
                if l0_result:
                    l1_result = self.execute_level1(query, l0_result)
                else:
                    l1_result = self.execute_level1(query, {})
                result['level1'] = l1_result
            
            # Level 2
            if use_l2:
                if not l0_result:
                    l0_result = self.router.route(query) if self.router else {'C': 0, 'I': 0, 'sigma_joint': 0}
                if not l1_result:
                    l1_result = self.execute_level1(query, l0_result) if self.documents else {'I_mean': 0.5, 'sigma_I': 0}
                
                l2_result = self.execute_level2(query, l0_result, l1_result)
                result['level2'] = l2_result
            
            # Determine display result (use highest level)
            if l2_result:
                display_result = {**l0_result, **l1_result, **l2_result}
            elif l1_result:
                display_result = {**l0_result, **l1_result}
            elif l0_result:
                display_result = l0_result
            else:
                display_result = {}
            
            elapsed = (time.time() - start_time) * 1000  # ms
            
            # Update UI
            self.update_results(query, display_result, elapsed, result)
            
            self.status_bar.config(text=f"完成 ({elapsed:.2f}ms)")
            
        except Exception as e:
            import traceback
            messagebox.showerror("错误", f"路由执行失败:\n{str(e)}\n\n{traceback.format_exc()}")
            self.status_bar.config(text=f"错误: {e}")
            
    def execute_level1(self, query: str, level0_result: dict) -> dict:
        """Execute Level 1 retrieval"""
        # Initialize Level 1 router if not already done
        if self.level1_router is None:
            self.level1_router = Level1Router(documents=self.documents)
        
        # Execute retrieval
        l1_result = self.level1_router.verify(query, level0_result)
        
        return l1_result
    
    def execute_level2(self, query: str, level0_result: dict, level1_result: dict) -> dict:
        """Execute Level 2 LLM arbitration"""
        # Initialize Level 2 router if not already done
        if self.level2_router is None:
            self.level2_router = Level2Router(use_dual_probe=False)  # 单探针模式更快
        
        # Build prompt construction info for display
        prompt_builder = PromptBuilder()
        context = build_level2_context(query, level0_result, level1_result)
        system_prompt = prompt_builder.get_system_prompt("ci_evaluation")
        user_prompt = prompt_builder.build_ci_evaluation_prompt(context)
        
        # Execute arbitration
        l2_result = self.level2_router.arbitrate(query, level0_result, level1_result)
        
        # Convert to dict for JSON serialization
        return {
            'C': l2_result.C,
            'I': l2_result.I,
            'C_continuous': l2_result.C_continuous,
            'I_continuous': l2_result.I_continuous,
            'confidence': l2_result.confidence,
            'sigma_c': l2_result.sigma_c,
            'sigma_i': l2_result.sigma_i,
            'sigma_joint': l2_result.sigma_joint,
            'escalate': l2_result.escalate,
            'escalate_reason': l2_result.escalate_reason,
            'mode': l2_result.mode,
            'reasoning': l2_result.reasoning,
            'probe_consistency': l2_result.probe_consistency,
            'conflict_with_l1': l2_result.conflict_with_l1,
            'latency_ms': l2_result.latency_ms,
            'cost_usd': l2_result.cost_usd,
            'model_used': l2_result.model_used,
            'parse_failures': l2_result.parse_failures,
            # Additional debug info for GUI
            '_debug': {
                'query': query,
                'system_prompt': system_prompt,
                'user_prompt': user_prompt,
                'level0_input': level0_result,
                'level1_input': level1_result,
                'context_summary': {
                    'level0_C': context.level0.C,
                    'level0_I': context.level0.I,
                    'level0_sigma_joint': context.level0.sigma_joint,
                    'level0_mode': context.level0.mode,
                    'level1_I_mean': context.level1.I_mean,
                    'level1_sigma_I': context.level1.sigma_I,
                    'level1_conflict': context.level1.conflict_detected,
                    'doc_count': len(context.retrieval_evidence.get('top_documents', []))
                }
            }
        }
            
    def update_results(self, query: str, result: dict, elapsed_ms: float, full_result: dict = None):
        """Update the UI with results"""
        # Update summary tab
        C = result.get('C', '-')
        I = result.get('I', result.get('I_mean', 0))
        
        if C != '-':
            zone = self.router.get_zone(C, I if isinstance(I, int) else int(I >= 0.7))
        else:
            zone = '-'
        
        self.c_label.config(text=f"{C} ({'High' if C == 1 else 'Low'})" if C != '-' else "-")
        self.i_label.config(text=f"{I} ({'Sufficient' if I == 1 else 'Insufficient'})" if isinstance(I, int) else f"{I:.3f}")
        self.zone_label.config(text=f"Zone {zone}" if zone != '-' else "-",
                              foreground=self.get_zone_color(zone) if zone != '-' else "black")
        
        # Update confidence
        sigma_c = result.get('sigma_c', 0)
        sigma_i = result.get('sigma_i', result.get('sigma_I', 0))
        sigma_joint = result.get('sigma_joint', 0)
        
        self.sigma_c_label.config(text=f"{sigma_c:.3f}")
        self.sigma_c_bar['value'] = sigma_c * 100
        
        self.sigma_i_label.config(text=f"{sigma_i:.3f}")
        self.sigma_i_bar['value'] = sigma_i * 100
        
        self.sigma_joint_label.config(text=f"{sigma_joint:.3f}")
        self.sigma_joint_bar['value'] = sigma_joint * 100
        
        # Color code confidence
        if sigma_joint >= 0.7:
            self.sigma_joint_label.config(foreground="green")
        elif sigma_joint >= 0.5:
            self.sigma_joint_label.config(foreground="orange")
        else:
            self.sigma_joint_label.config(foreground="red")
        
        # Update Level 1 specific results
        if 'I_mean' in result:
            self.i_mean_label.config(text=f"{result['I_mean']:.3f}")
            self.sigma_i_fused_label.config(text=f"{result.get('sigma_I', 0):.3f}")
            
            conflict = result.get('conflict_detected', False)
            self.conflict_label.config(text="是" if conflict else "否",
                                      foreground="red" if conflict else "green")
            
            sources = list(result.get('source_weights', {}).keys())
            self.sources_label.config(text=", ".join(sources) if sources else "无")
            
            # Show reliabilities
            reliabilities = result.get('source_reliabilities', {})
            if reliabilities:
                rel_strs = [f"{s[:3]}:{v:.2f}" for s, v in reliabilities.items()]
                self.reliability_label.config(text=" | ".join(rel_strs))
            else:
                self.reliability_label.config(text="-")
        else:
            self.i_mean_label.config(text="-")
            self.sigma_i_fused_label.config(text="-")
            self.conflict_label.config(text="-")
            self.sources_label.config(text="-")
            self.reliability_label.config(text="-")
        
        # Update decision
        escalate = result.get('escalate', False)
        if escalate:
            if self.use_level2_var.get():
                self.decision_label.config(text="触发 Level 2 回退策略", foreground="red")
            elif self.use_level1_var.get():
                self.decision_label.config(text="升级到 Level 2", foreground="orange")
            else:
                self.decision_label.config(text="升级到 Level 1", foreground="orange")
        else:
            self.decision_label.config(text=f"直接路由到 Zone {zone}", foreground="green")
            
        self.mode_label.config(text=result.get('mode', 'Unknown'))
        self.time_label.config(text=f"{elapsed_ms:.2f} ms")
        
        # Update features tab (from Level 0)
        if 'level0' in full_result and full_result['level0']:
            features = full_result['level0'].get('features', [])
            for i, item in enumerate(self.feature_tree.get_children()):
                if i < len(features):
                    name, cn_name, desc = self.feature_names[i]
                    self.feature_tree.item(item, values=(i, f"{name}\n{cn_name}", f"{features[i]:.4f}", desc))
        
        # Update retrieval tab (Level 1)
        if 'level1' in full_result and full_result['level1']:
            self.update_retrieval_tab(full_result['level1'])
        
        # Update Level 2 tab
        if 'level2' in full_result and full_result['level2']:
            self.update_level2_tab(full_result['level2'])
        
        # Update JSON tab
        result_with_meta = {
            "query": query,
            "processing_time_ms": elapsed_ms,
            **(full_result or result)
        }
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", json.dumps(result_with_meta, indent=2, ensure_ascii=False, default=str))
        
        # Add to history
        modes = []
        if self.use_level0_var.get():
            modes.append("L0")
        if self.use_level1_var.get():
            modes.append("L1")
        if self.use_level2_var.get():
            modes.append("L2")
        mode_str = "+".join(modes) if modes else "None"
        self.add_to_history(query, zone, escalate, mode_str)
        
    def update_retrieval_tab(self, l1_result: dict):
        """Update Level 1 retrieval tab"""
        # Overview
        overview_text = f"""=== Level 1 混合检索融合结果 ===

融合后 I_mean: {l1_result.get('I_mean', 0):.3f}
融合后 sigma_I: {l1_result.get('sigma_I', 0):.3f}
冲突检测: {'是' if l1_result.get('conflict_detected') else '否'}
数据源权重: {json.dumps(l1_result.get('source_weights', {}), ensure_ascii=False)}

=== Level 0 输入 ===
C: {l1_result.get('C', '-')}
I (Level 0): {l1_result.get('I_level0', 0):.3f}
sigma_joint: {l1_result.get('sigma_joint', 0):.3f}
"""
        self.retrieval_text.delete("1.0", tk.END)
        self.retrieval_text.insert("1.0", overview_text)
        
        # Vector results
        evidence = l1_result.get('retrieval_evidence', {})
        vector = evidence.get('vector')
        if vector:
            vector_text = f"""=== 向量检索结果 ===

最大相似度 (sim_max): {vector.get('sim_max', 0):.3f}
差距 (gap): {vector.get('gap', 0):.3f}
熵 (entropy): {vector.get('entropy', 0):.3f}

检索结果:
"""
            for i, r in enumerate(vector.get('results', [])[:5], 1):
                vector_text += f"\n{i}. 相似度: {r.get('similarity', 0):.3f}\n"
                vector_text += f"   内容: {r.get('content', '')[:100]}...\n"
        else:
            vector_text = "向量检索未执行或无结果"
        self.vector_text.delete("1.0", tk.END)
        self.vector_text.insert("1.0", vector_text)
        
        # Keyword results
        keyword = evidence.get('keyword')
        if keyword:
            keyword_text = f"""=== 关键词检索结果 ===

最大分数 (score_max): {keyword.get('score_max', 0):.2f}
覆盖率 (coverage): {keyword.get('coverage', 0):.2f}
匹配词: {', '.join(keyword.get('matched_terms', [])[:10])}

检索结果:
"""
            for i, r in enumerate(keyword.get('results', [])[:5], 1):
                keyword_text += f"\n{i}. 分数: {r.get('score', 0):.2f}\n"
                keyword_text += f"   内容: {r.get('content', '')[:100]}...\n"
                if r.get('matched_terms'):
                    keyword_text += f"   匹配: {', '.join(r.get('matched_terms', [])[:5])}\n"
        else:
            keyword_text = "关键词检索未执行或无结果"
        self.keyword_text.delete("1.0", tk.END)
        self.keyword_text.insert("1.0", keyword_text)
        
        # Top documents
        # Clear existing
        for item in self.docs_tree.get_children():
            self.docs_tree.delete(item)
        
        # Add documents
        docs = evidence.get('top_documents', [])
        for i, doc in enumerate(docs[:10], 1):
            self.docs_tree.insert('', 'end', values=(
                i,
                doc.get('source', 'unknown'),
                f"{doc.get('score', 0):.3f}",
                doc.get('content', '')[:80] + '...' if len(doc.get('content', '')) > 80 else doc.get('content', '')
            ))
        
    def update_level2_tab(self, l2_result: dict):
        """Update Level 2 LLM arbitration tab"""
        # LLM Result
        result_text = f"""=== Level 2 LLM 仲裁结果 ===

复杂度 (C): {l2_result.get('C', '-')} ({'高' if l2_result.get('C') == 1 else '低' if l2_result.get('C') == 0 else '未知'})
信息充分性 (I): {l2_result.get('I', '-')} ({'充分' if l2_result.get('I') == 1 else '不足' if l2_result.get('I') == 0 else '未知'})

置信度:
  - Confidence: {l2_result.get('confidence', 0):.3f}
  - Sigma C: {l2_result.get('sigma_c', 0):.3f}
  - Sigma I: {l2_result.get('sigma_i', 0):.3f}
  - Sigma Joint: {l2_result.get('sigma_joint', 0):.3f}

执行模式: {l2_result.get('mode', 'Unknown')}
是否升级: {'是' if l2_result.get('escalate') else '否'}
升级原因: {l2_result.get('escalate_reason', 'N/A')}

与 Level 1 冲突: {'是' if l2_result.get('conflict_with_l1') else '否'}
探针一致性: {l2_result.get('probe_consistency', 0):.3f}
解析失败次数: {l2_result.get('parse_failures', 0)}
"""
        self.level2_result_text.delete("1.0", tk.END)
        self.level2_result_text.insert("1.0", result_text)
        
        # Reasoning
        reasoning = l2_result.get('reasoning', '无推理过程')
        self.level2_reasoning_text.delete("1.0", tk.END)
        self.level2_reasoning_text.insert("1.0", reasoning)
        
        # Prompt Construction
        debug_info = l2_result.get('_debug', {})
        if debug_info:
            system_prompt = debug_info.get('system_prompt', 'N/A')
            user_prompt = debug_info.get('user_prompt', 'N/A')
            context_summary = debug_info.get('context_summary', {})
            level0_input = debug_info.get('level0_input', {})
            level1_input = debug_info.get('level1_input', {})
            
            prompt_text = f"""=== Level 2 提示词构建详情 ===

【调用方法】
- 使用类: Level2Router.arbitrate()
- 提示词构建: PromptBuilder.build_ci_evaluation_prompt()
- 上下文构建: build_level2_context()

【输入参数摘要】
Level 0 输入:
  - C (复杂度): {context_summary.get('level0_C', 'N/A')}
  - I (信息充分性): {context_summary.get('level0_I', 'N/A')}
  - Sigma Joint: {context_summary.get('level0_sigma_joint', 'N/A'):.3f}
  - 模式: {context_summary.get('level0_mode', 'N/A')}

Level 1 输入:
  - I_mean: {context_summary.get('level1_I_mean', 'N/A'):.3f}
  - Sigma I: {context_summary.get('level1_sigma_I', 'N/A'):.3f}
  - 冲突检测: {'是' if context_summary.get('level1_conflict') else '否'}
  - Top 文档数: {context_summary.get('doc_count', 0)}

【System Prompt (系统提示词)】
{'='*60}
{system_prompt}
{'='*60}

【User Prompt (用户提示词)】
{'='*60}
{user_prompt}
{'='*60}

【原始 Level 0 结果】
{json.dumps(level0_input, indent=2, ensure_ascii=False)}

【原始 Level 1 结果】
{json.dumps(level1_input, indent=2, ensure_ascii=False, default=str)}
"""
        else:
            prompt_text = "无调试信息（可能 Level 2 未实际执行或执行失败）"
        
        self.level2_prompt_text.delete("1.0", tk.END)
        self.level2_prompt_text.insert("1.0", prompt_text)
        
        # Metrics
        metrics_text = f"""=== Level 2 性能指标 ===

延迟与成本:
  - LLM 延迟: {l2_result.get('latency_ms', 0):.2f} ms
  - API 成本: ${l2_result.get('cost_usd', 0):.6f}
  - 使用模型: {l2_result.get('model_used', 'Unknown')}

总计指标:
"""
        if self.level2_router:
            metrics = self.level2_router.get_metrics()
            metrics_text += f"""  - 总请求数: {metrics.get('total_requests', 0)}
  - 总升级数: {metrics.get('total_escapes', 0)}
  - 升级率: {metrics.get('escape_rate', 0):.2%}
  - 总成本: ${metrics.get('total_cost_usd', 0):.6f}
  - 平均延迟: {metrics.get('avg_latency_ms', 0):.2f} ms
"""
        self.level2_metrics_text.delete("1.0", tk.END)
        self.level2_metrics_text.insert("1.0", metrics_text)
        
    def get_zone_color(self, zone: str) -> str:
        """Get color for zone"""
        colors = {
            'A': 'purple',
            'B': 'orange',
            'C': 'green',
            'D': 'blue'
        }
        return colors.get(zone, 'black')
        
    def add_to_history(self, query: str, zone: str, escalate: bool, mode: str):
        """Add entry to history"""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        
        self.history_tree.insert('', 0, values=(
            time_str,
            query[:40] + '...' if len(query) > 40 else query,
            zone,
            mode,
            '是' if escalate else '否'
        ))
        
        # Keep only last 100 entries
        if len(self.history_tree.get_children()) > 100:
            self.history_tree.delete(self.history_tree.get_children()[-1])
            
    def clear_history(self):
        """Clear history"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
    def clear_input(self):
        """Clear input field"""
        self.query_text.delete("1.0", tk.END)
        self.query_text.focus()
        
    def show_examples(self):
        """Show example queries menu"""
        examples = [
            "什么是Python?",
            "查询订单号12345的状态",
            "分析某医药公司的Kubernetes部署合规性，考虑成本、安全性和法规要求",
            "如何配置Docker容器?",
            "比较微服务架构和单体架构在性能、可维护性和部署复杂度方面的差异",
            "安装",
            # Medical examples for Level 1
            "--- 医疗案例 (Level 1) ---",
            "患者咳嗽有铁锈色痰，胸痛发热",
            "晚上喘不过气，能听到哮鸣音",
            "胸口压榨性疼痛，劳动后发作，休息缓解",
            "ST段抬高 心肌酶升高 胸痛",
            "半边身子动不了，说话不清楚",
            # Complex examples for Level 2
            "--- 复杂查询 (Level 2) ---",
            "设计一个支持百万并发的电商系统，考虑数据库选型、缓存策略、消息队列和容灾方案",
            "分析2024年全球 pharmaceutical 行业的监管趋势及其对中国创新药企业出海战略的影响",
        ]
        
        # Create popup menu
        menu = tk.Menu(self.root, tearoff=0)
        for ex in examples:
            if ex.startswith("---"):
                menu.add_separator()
                menu.add_command(label=ex, state='disabled')
            else:
                menu.add_command(label=ex[:45] + '...' if len(ex) > 45 else ex,
                               command=lambda q=ex: self.set_query(q))
        
        # Show menu
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()
            
    def set_query(self, query: str):
        """Set query text"""
        self.query_text.delete("1.0", tk.END)
        self.query_text.insert("1.0", query)
        self.execute_routing()
        
    def reload_routers(self):
        """Reload routers"""
        self.status_bar.config(text="重新加载模型...")
        self.root.update()
        
        # Reset routers
        self.level1_router = None
        self.level2_router = None
        
        self.init_routers()
        self.status_label.config(text=self.router_status)
        self.level1_status_label.config(text=self.level1_status)
        self.level2_status_label.config(text=self.level2_status)
        
        messagebox.showinfo("重新加载", f"Level 0: {self.router_status}\nLevel 1: {self.level1_status}\nLevel 2: {self.level2_status}")
        self.status_bar.config(text="就绪")
    
    # ==================== V2 Orchestrator Methods ====================
    
    def build_orchestrator_tab(self):
        """Build the Orchestrator V2 tab"""
        # Status frame
        status_frame = ttk.LabelFrame(self.orchestrator_frame, text="V2 协调器状态", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(status_frame, text=f"状态: {getattr(self, 'orchestrator_v2_status', '未初始化')}",
                 font=('Arial', 10)).pack(anchor=tk.W)
        ttk.Label(status_frame, text="特性: Zone B/D 必须携带 orchestrator_guide | 支持多策略 [clarify, decompose] | 最大 2 轮转区",
                 font=('Arial', 9), foreground="gray").pack(anchor=tk.W, pady=(5, 0))
        
        # Execute button
        btn_frame = ttk.Frame(self.orchestrator_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(btn_frame, text="执行 V2 协调器",
                  command=self.execute_orchestrator_v2).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="模拟多轮交互",
                  command=self.simulate_v2_session).pack(side=tk.LEFT)
        
        # Result display
        result_frame = ttk.LabelFrame(self.orchestrator_frame, text="协调器输出", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        self.orchestrator_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD,
                                                          font=('Consolas', 10))
        self.orchestrator_text.pack(fill=tk.BOTH, expand=True)
        self.orchestrator_text.insert("1.0", "启用 V2 协调器后，此处将显示:\n\n"
                                     "1. 初始 Zone 判定\n"
                                     "2. orchestrator_guide (Level 2 生成)\n"
                                     "3. 推荐策略 [clarify/decompose]\n"
                                     "4. 转区计划和执行结果")
    
    def execute_orchestrator_v2(self):
        """Execute V2 orchestrator"""
        if not ORCHESTRATOR_V2_AVAILABLE:
            messagebox.showerror("错误", "SmartOrchestratorV2 不可用")
            return
        
        if not self.orchestrator_v2:
            messagebox.showerror("错误", "V2 协调器未初始化")
            return
        
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("输入为空", "请输入查询语句")
            return
        
        self.status_bar.config(text="执行 V2 协调器...")
        self.root.update()
        
        try:
            start_time = time.time()
            
            # Initialize L1 router if needed
            if self.level1_router is None and self.documents:
                self.level1_router = Level1Router(documents=self.documents)
            
            # Initialize L2 router if needed
            if self.level2_router is None:
                self.level2_router = Level2Router(use_dual_probe=False)
            
            # Update orchestrator with current routers
            self.orchestrator_v2.l1_router = self.level1_router
            self.orchestrator_v2.l2_router = self.level2_router
            
            # Execute V2 orchestrator
            result = self.orchestrator_v2.process(query, session_id=f"gui_{int(start_time)}")
            
            elapsed = (time.time() - start_time) * 1000
            
            # Display result
            self.update_orchestrator_tab(result, elapsed)
            
            self.status_bar.config(text=f"V2 协调器完成 ({elapsed:.2f}ms)")
            
        except Exception as e:
            import traceback
            messagebox.showerror("错误", f"V2 协调器执行失败:\n{str(e)}\n\n{traceback.format_exc()}")
            self.status_bar.config(text=f"错误: {e}")
    
    def update_orchestrator_tab(self, result: dict, elapsed_ms: float):
        """Update orchestrator tab with result"""
        status = result.get('status', 'unknown')
        
        # Safely format sigma_joint
        sigma_joint = result.get('ci', {}).get('sigma_joint', '-')
        if isinstance(sigma_joint, (int, float)):
            sigma_joint_str = f"{sigma_joint:.3f}"
        else:
            sigma_joint_str = str(sigma_joint)
        
        text = f"""=== V2 协调器执行结果 ===

状态: {status}
执行时间: {elapsed_ms:.2f} ms
转区轮次: {result.get('transition_round', 0)} / {result.get('max_rounds', 2)}

=== CI 评估 ===
Zone: {result.get('zone', '-')} {'(最优区)' if result.get('zone') in ['A', 'C'] else '(需转区)'}
C (复杂度): {result.get('ci', {}).get('C', '-')}
I (信息充分): {result.get('ci', {}).get('I', '-')}
sigma_joint: {sigma_joint_str}

"""
        
        if status == 'transition_required':
            text += f"""=== 转区计划 ===
当前区域: {result.get('current_zone', '-')}
目标区域: {result.get('target_zone', '-')}
主策略: {result.get('primary_strategy', '-')}
可用策略: {', '.join(result.get('available_strategies', []))}
用户可选择: {'是' if result.get('user_selectable') else '否'}

"""
            if 'clarification' in result:
                clarification = result['clarification']
                text += f"""=== 信息补充 (Clarify) ===
缺失信息:
"""
                for info in clarification.get('missing_info', []):
                    text += f"  - {info}\n"
                text += f"\n提示模板:\n{clarification.get('prompt', '')}\n"
            
            if 'decomposition' in result:
                decomposition = result['decomposition']
                text += f"""\n=== 问题分解 (Decompose) ===
子问题数量: {len(decomposition.get('sub_problems', []))}
聚合目标: Zone {decomposition.get('aggregation_target', '-')}

子问题列表:
"""
                for sp in decomposition.get('sub_problems', []):
                    text += f"  [{sp.get('id')}] {sp.get('query')}\n"
        
        elif status == 'success':
            text += f"""=== 执行配置 ===
已到达最优区，可直接执行:

"""
            config = result.get('execution_config', {})
            text += f"  描述: {config.get('description', '-')}\n"
            text += f"  Max Tokens: {config.get('max_tokens', '-')}\n"
            text += f"  Temperature: {config.get('temperature', '-')}\n"
            text += f"  Retrieval Streams: {config.get('retrieval_streams', '-')}\n"
            text += f"  Verification: {'是' if config.get('verification') else '否'}\n"
        
        elif status == 'fallback':
            text += f"""=== 回退执行 ===
原因: {result.get('reason', '未知')}
使用保守策略在 Zone B 执行
"""
        
        self.orchestrator_text.delete("1.0", tk.END)
        self.orchestrator_text.insert("1.0", text)
    
    def simulate_v2_session(self):
        """Simulate a multi-round V2 session"""
        if not ORCHESTRATOR_V2_AVAILABLE or not self.orchestrator_v2:
            messagebox.showerror("错误", "V2 协调器不可用")
            return
        
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            query = "How to use this medicine?"
        
        # Initialize L1/L2 routers if needed
        if self.level1_router is None and self.documents:
            self.level1_router = Level1Router(documents=self.documents)
        
        if self.level2_router is None:
            self.level2_router = Level2Router(use_dual_probe=False)
        
        # Update orchestrator with routers
        self.orchestrator_v2.l1_router = self.level1_router
        self.orchestrator_v2.l2_router = self.level2_router
        
        # Create a simulation
        session_id = f"sim_{int(time.time())}"
        
        text = f"""=== V2 协调器多轮会话模拟 ===
会话 ID: {session_id}
原始查询: {query}

"""
        
        # Round 1: Initial query
        text += "【第 1 轮】初始查询\n"
        text += f"  用户: {query}\n"
        
        try:
            result = self.orchestrator_v2.process(query, session_id=session_id)
            text += f"  状态: {result.get('status')}\n"
            text += f"  Zone: {result.get('zone', result.get('current_zone', '-'))}\n"
            
            status = result.get('status')
            if status == 'transition_required':
                text += f"  需要: {result.get('primary_strategy')}\n"
                if 'clarification' in result:
                    missing = result['clarification'].get('missing_info', [])
                    text += f"  缺失信息: {', '.join(missing)}\n"
                
                # Simulate user providing info
                text += "\n【第 2 轮】用户提供信息\n"
                text += "  用户: 提供了部分信息\n"
                
                result2 = self.orchestrator_v2.continue_with_info(session_id, {
                    'medicine': 'Amoxicillin',
                    'age': '35'
                })
                
                text += f"  状态: {result2.get('status')}\n"
                text += f"  Zone: {result2.get('zone', result2.get('current_zone', '-'))}\n"
                
                if result2.get('status') == 'success':
                    text += "  ✓ 到达最优区，可以执行\n"
            elif status == 'success':
                text += "  ✓ 直接到达最优区\n"
            elif status == 'fallback':
                text += f"  ⚠ 回退执行: {result.get('reason', '未知原因')}\n"
            else:
                text += f"  ? 未知状态: {status}\n"
                
        except Exception as e:
            text += f"  错误: {e}\n"
        
        self.orchestrator_text.delete("1.0", tk.END)
        self.orchestrator_text.insert("1.0", text)
        
    def run(self):
        """Run the application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    if not TKINTER_AVAILABLE:
        print("Error: tkinter is required but not available.")
        print("Please install Python with tkinter support.")
        sys.exit(1)
        
    app = CIRouterTestWindow()
    app.run()


if __name__ == '__main__':
    main()
