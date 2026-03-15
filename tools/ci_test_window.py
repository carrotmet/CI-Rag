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


class CIRouterTestWindow:
    """CI-RAG-ROUTER 测试窗口主类"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CI-RAG-ROUTER 测试工具")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Initialize router
        self.router = None
        self.init_router()
        
        # Build UI
        self.build_ui()
        
    def init_router(self):
        """Initialize Level 0 router"""
        try:
            self.router = Level0Router()
            self.router_status = self.router.get_status().value
        except Exception as e:
            self.router_status = f"Error: {e}"
            
    def build_ui(self):
        """Build the user interface"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)  # Result area expands
        
        # ===== Header Section =====
        header_frame = ttk.LabelFrame(main_frame, text="系统状态", padding="5")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        ttk.Label(header_frame, text="Level 0 状态:").grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(header_frame, text=self.router_status, 
                                     font=('Arial', 10, 'bold'))
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Reload button
        ttk.Button(header_frame, text="重新加载模型", 
                  command=self.reload_router).grid(row=0, column=2, padx=(10, 0))
        
        # ===== Input Section =====
        input_frame = ttk.LabelFrame(main_frame, text="查询输入", padding="5")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # Query input
        self.query_text = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.query_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.query_text.insert("1.0", "输入查询语句，例如：分析某医药公司的Kubernetes部署合规性")
        self.query_text.bind('<Return>', self.on_enter_pressed)
        
        # Buttons frame
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Button(btn_frame, text="执行路由 (Enter)", 
                  command=self.execute_routing).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="清空", 
                  command=self.clear_input).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="示例查询 ▼", 
                  command=self.show_examples).pack(side=tk.LEFT)
        
        # ===== Results Section =====
        result_frame = ttk.LabelFrame(main_frame, text="路由结果", padding="5")
        result_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
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
        
        # Tab 3: JSON view
        self.json_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.json_frame, text="原始数据")
        self.build_json_tab()
        
        # Tab 4: History
        self.history_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.history_frame, text="历史记录")
        self.build_history_tab()
        
        # Status bar
        self.status_bar = ttk.Label(main_frame, text="就绪", relief=tk.SUNKEN)
        self.status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Store history
        self.history = []
        
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
            
    def build_json_tab(self):
        """Build the raw JSON tab"""
        self.json_text = scrolledtext.ScrolledText(self.json_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.json_text.pack(fill=tk.BOTH, expand=True)
        self.json_text.insert("1.0", "执行查询后将显示原始 JSON 数据")
        
    def build_history_tab(self):
        """Build the history tab"""
        # History list
        columns = ('time', 'query', 'zone', 'escalate')
        self.history_tree = ttk.Treeview(self.history_frame, columns=columns, show='headings')
        
        self.history_tree.heading('time', text='时间')
        self.history_tree.heading('query', text='查询')
        self.history_tree.heading('zone', text='区域')
        self.history_tree.heading('escalate', text='升级')
        
        self.history_tree.column('time', width=60)
        self.history_tree.column('query', width=400)
        self.history_tree.column('zone', width=50, anchor='center')
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
        """Execute the routing process"""
        query = self.query_text.get("1.0", tk.END).strip()
        
        if not query:
            messagebox.showwarning("输入为空", "请输入查询语句")
            return
            
        self.status_bar.config(text=f"正在处理: {query[:50]}...")
        self.root.update()
        
        try:
            # Measure time
            start_time = time.time()
            
            # Execute routing
            result = self.router.route(query)
            
            elapsed = (time.time() - start_time) * 1000  # ms
            
            # Update UI
            self.update_results(query, result, elapsed)
            
            self.status_bar.config(text=f"完成 ({elapsed:.2f}ms)")
            
        except Exception as e:
            messagebox.showerror("错误", f"路由执行失败:\n{str(e)}")
            self.status_bar.config(text=f"错误: {e}")
            
    def update_results(self, query: str, result: dict, elapsed_ms: float):
        """Update the UI with results"""
        # Update summary tab
        C = result['C']
        I = result['I']
        zone = self.router.get_zone(C, I)
        
        self.c_label.config(text=f"{C} ({'High' if C == 1 else 'Low'})")
        self.i_label.config(text=f"{I} ({'Sufficient' if I == 1 else 'Insufficient'})")
        self.zone_label.config(text=f"Zone {zone}", 
                              foreground=self.get_zone_color(zone))
        
        # Update confidence
        sigma_c = result['sigma_c']
        sigma_i = result['sigma_i']
        sigma_joint = result['sigma_joint']
        
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
        
        # Update decision
        escalate = result['escalate']
        if escalate:
            self.decision_label.config(text="升级到 Level 1", foreground="orange")
        else:
            self.decision_label.config(text=f"直接路由到 Zone {zone}", foreground="green")
            
        self.mode_label.config(text=result.get('mode', 'Unknown'))
        self.time_label.config(text=f"{elapsed_ms:.2f} ms")
        
        # Update features tab
        features = result.get('features', [])
        for i, item in enumerate(self.feature_tree.get_children()):
            if i < len(features):
                name, cn_name, desc = self.feature_names[i]
                self.feature_tree.item(item, values=(i, f"{name}\n{cn_name}", f"{features[i]:.4f}", desc))
            
        # Update JSON tab
        result_with_meta = {
            "query": query,
            "processing_time_ms": elapsed_ms,
            **result
        }
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", json.dumps(result_with_meta, indent=2, ensure_ascii=False))
        
        # Add to history
        self.add_to_history(query, zone, escalate)
        
    def get_zone_color(self, zone: str) -> str:
        """Get color for zone"""
        colors = {
            'A': 'purple',
            'B': 'orange',
            'C': 'green',
            'D': 'blue'
        }
        return colors.get(zone, 'black')
        
    def add_to_history(self, query: str, zone: str, escalate: bool):
        """Add entry to history"""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        
        self.history_tree.insert('', 0, values=(
            time_str,
            query[:50] + '...' if len(query) > 50 else query,
            zone,
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
        ]
        
        # Create popup menu
        menu = tk.Menu(self.root, tearoff=0)
        for ex in examples:
            menu.add_command(label=ex[:40] + '...' if len(ex) > 40 else ex,
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
        
    def reload_router(self):
        """Reload router"""
        self.status_bar.config(text="重新加载模型...")
        self.root.update()
        
        self.init_router()
        self.status_label.config(text=self.router_status)
        
        messagebox.showinfo("重新加载", f"路由器状态: {self.router_status}")
        self.status_bar.config(text="就绪")
        
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
