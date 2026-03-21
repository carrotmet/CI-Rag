#!/usr/bin/env python3
"""
CI-RAG-ROUTER V4 测试窗口 (简化版)

专注V4架构功能：
- Level 012 逃逸层 → 初始Zone判定
- Zone A/B/D 自治执行
- Orchestrator V4 转区校验
- Zone C 统一出口（大脑）

Usage:
    python tools/ci_test_window_v4.py
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    print("Error: tkinter not available.")
    sys.exit(1)

# Import V4 Architecture
try:
    from ci_architecture.v4_pipeline import CIRouterPipelineV4, PipelineResult
    from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4, Zone, CIState
    from ci_architecture.zones import ZoneAHandler, ZoneBHandler, ZoneCHandler, ZoneDHandler
    from ci_architecture.zones.zone_c import ReasoningStrategy
    from ci_architecture.common import GuideGenerator, StrategyManager, SubProblemQueue
    from ci_architecture.common.subproblem_queue import SubProblemResult
    from ci_architecture.level0 import Level0Router
    from ci_architecture.level1 import Level1Router
    from ci_architecture.level2 import Level2Router
    V4_AVAILABLE = True
except ImportError as e:
    V4_AVAILABLE = False
    print(f"Warning: V4 Architecture not available: {e}")


class CIRouterTestWindowV4:
    """CI-RAG-ROUTER V4 测试窗口"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CI-RAG-ROUTER V4 测试工具")
        self.root.geometry("1100x800")
        self.root.minsize(900, 700)
        
        # Initialize
        self.router = None
        self.level1_router = None
        self.level2_router = None
        self.v4_pipeline = None
        self.orchestrator_v4 = None
        self.documents = None
        
        self.init_routers()
        self.build_ui()
        
    def init_routers(self):
        """Initialize routers"""
        # Level 0
        try:
            self.router = Level0Router()
            self.router_status = self.router.get_status().value
        except Exception as e:
            self.router_status = f"Error: {e}"
        
        # Level 1
        try:
            from data.medical_symptoms import get_medical_dataset
            self.documents = get_medical_dataset()
            self.level1_status = f"就绪 ({len(self.documents)}文档)"
        except Exception as e:
            self.level1_status = f"未就绪"
            self.documents = None
        
        # Level 2
        try:
            api_key = os.environ.get("CI_LLM_API_KEY")
            self.level2_status = "就绪" if api_key else "未配置API Key"
        except Exception as e:
            self.level2_status = f"未就绪"
        
        # V4 Pipeline
        if V4_AVAILABLE:
            try:
                self.v4_pipeline = CIRouterPipelineV4(
                    l0_router=self.router,
                    l1_router=None,
                    l2_router=None,
                )
                self.v4_status = "就绪"
            except Exception as e:
                self.v4_status = f"未就绪"
        else:
            self.v4_status = "不可用"
            
        # V4 Orchestrator
        if V4_AVAILABLE:
            try:
                self.orchestrator_v4 = OrchestratorV4()
                self.orchestrator_v4_status = "就绪"
            except Exception as e:
                self.orchestrator_v4_status = f"未就绪"
        else:
            self.orchestrator_v4_status = "不可用"
        
    def build_ui(self):
        """Build UI"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # ===== Status Panel =====
        self.build_status_panel(main_frame)
        
        # ===== Input Section =====
        self.build_input_section(main_frame)
        
        # ===== V4 Test Buttons =====
        self.build_v4_test_buttons(main_frame)
        
        # ===== Results Notebook =====
        self.build_results_notebook(main_frame)
        
        # ===== Status Bar =====
        self.status_bar = ttk.Label(main_frame, text="就绪", relief=tk.SUNKEN)
        self.status_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
    def build_status_panel(self, parent):
        """Build status panel"""
        header = ttk.LabelFrame(parent, text="系统状态", padding="5")
        header.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        statuses = [
            ("L0:", self.router_status, 0, 0),
            ("L1:", self.level1_status, 0, 2),
            ("L2:", self.level2_status, 0, 4),
            ("V4 Pipeline:", self.v4_status, 1, 0),
            ("V4 Orchestrator:", self.orchestrator_v4_status, 1, 2),
        ]
        
        for label, status, row, col in statuses:
            ttk.Label(header, text=label).grid(row=row, column=col, sticky=tk.W, padx=(10 if col > 0 else 0, 0))
            ttk.Label(header, text=status, font=('Arial', 9, 'bold')).grid(row=row, column=col+1, sticky=tk.W, padx=(5, 20))
        
        ttk.Button(header, text="重新加载", command=self.reload_routers).grid(row=0, column=6, rowspan=2, padx=(10, 0))
        
    def build_input_section(self, parent):
        """Build input section"""
        input_frame = ttk.LabelFrame(parent, text="查询输入", padding="5")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # Query input
        self.query_text = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.query_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.query_text.insert("1.0", "输入查询语句...")
        self.query_text.bind('<Return>', self.on_enter_pressed)
        
        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.v4_pipeline_btn = ttk.Button(btn_frame, text="V4 Pipeline 执行", command=self.execute_v4_pipeline)
        self.v4_pipeline_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.v4_orch_btn = ttk.Button(btn_frame, text="V4 Orchestrator", command=self.execute_orchestrator_v4)
        self.v4_orch_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(btn_frame, text="清空", command=self.clear_input).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="示例▼", command=self.show_examples).pack(side=tk.LEFT)
        
    def build_v4_test_buttons(self, parent):
        """Build V4 test buttons"""
        v4_frame = ttk.LabelFrame(parent, text="V4 架构测试点", padding="5")
        v4_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        tests = [
            ("CI映射", self.test_ci_mapping),
            ("Zone D检索", self.test_zone_d),
            ("Zone A拆解", self.test_zone_a),
            ("Zone B混合", self.test_zone_b),
            ("Zone C直接", self.test_zone_c_direct),
            ("Zone C队列", self.test_zone_c_queue),
            ("策略升级", self.test_strategy_upgrade),
            ("转区校验", self.test_transition_validation),
        ]
        
        for i, (label, cmd) in enumerate(tests):
            ttk.Button(v4_frame, text=label, command=cmd).grid(
                row=0, column=i, padx=(5 if i > 0 else 10, 5), pady=5)
        
    def build_results_notebook(self, parent):
        """Build results notebook"""
        result_frame = ttk.LabelFrame(parent, text="执行结果", padding="5")
        result_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Tab 1: Summary
        self.summary_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.summary_frame, text="执行摘要")
        self.build_summary_tab()
        
        # Tab 2: V4 Pipeline
        self.v4_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.v4_frame, text="V4 Pipeline")
        self.v4_text = scrolledtext.ScrolledText(self.v4_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.v4_text.pack(fill=tk.BOTH, expand=True)
        self.v4_text.insert("1.0", "执行V4 Pipeline后将显示完整执行路径...")
        
        # Tab 3: Zone Details
        self.zone_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.zone_frame, text="Zone执行详情")
        self.build_zone_tab()
        
        # Tab 4: Orchestrator
        self.orch_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.orch_frame, text="Orchestrator")
        self.orch_text = scrolledtext.ScrolledText(self.orch_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.orch_text.pack(fill=tk.BOTH, expand=True)
        self.orch_text.insert("1.0", "Orchestrator转区校验结果...")
        
        # Tab 5: JSON
        self.json_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.json_frame, text="原始数据(JSON)")
        self.json_text = scrolledtext.ScrolledText(self.json_frame, wrap=tk.WORD, font=('Consolas', 9))
        self.json_text.pack(fill=tk.BOTH, expand=True)
        
    def build_summary_tab(self):
        """Build summary tab"""
        # CI Display
        ci_frame = ttk.LabelFrame(self.summary_frame, text="CI评估", padding="10")
        ci_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ci_frame, text="C(复杂度):").grid(row=0, column=0, sticky=tk.W)
        self.c_label = ttk.Label(ci_frame, text="-", font=('Arial', 12, 'bold'))
        self.c_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 20))
        
        ttk.Label(ci_frame, text="I(信息度):").grid(row=0, column=2, sticky=tk.W)
        self.i_label = ttk.Label(ci_frame, text="-", font=('Arial', 12, 'bold'))
        self.i_label.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(ci_frame, text="Zone:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.zone_label = ttk.Label(ci_frame, text="-", font=('Arial', 16, 'bold'), foreground="blue")
        self.zone_label.grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=(5, 0), pady=(10, 0))
        
        # Confidence
        conf_frame = ttk.LabelFrame(self.summary_frame, text="置信度", padding="10")
        conf_frame.pack(fill=tk.X, pady=(0, 10))
        
        for i, (label, attr) in enumerate([("σ_c:", "sigma_c"), ("σ_i:", "sigma_i"), ("σ_joint:", "sigma_joint")]):
            ttk.Label(conf_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=(2, 0))
            lbl = ttk.Label(conf_frame, text="-")
            lbl.grid(row=i, column=1, sticky=tk.W, padx=(5, 0))
            bar = ttk.Progressbar(conf_frame, length=200, mode='determinate', maximum=100)
            bar.grid(row=i, column=2, padx=(10, 0))
            setattr(self, f"{attr}_label", lbl)
            setattr(self, f"{attr}_bar", bar)
        
        # Execution Info
        info_frame = ttk.LabelFrame(self.summary_frame, text="执行信息", padding="10")
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text="执行路径:").grid(row=0, column=0, sticky=tk.W)
        self.path_label = ttk.Label(info_frame, text="-", font=('Consolas', 9))
        self.path_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(info_frame, text="耗时:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.time_label = ttk.Label(info_frame, text="-")
        self.time_label.grid(row=1, column=1, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
    def build_zone_tab(self):
        """Build zone execution tab"""
        zone_notebook = ttk.Notebook(self.zone_frame)
        zone_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Zone A
        zone_a = ttk.Frame(zone_notebook, padding="10")
        zone_notebook.add(zone_a, text="Zone A (拆解)")
        self.zone_a_text = scrolledtext.ScrolledText(zone_a, wrap=tk.WORD, font=('Consolas', 10))
        self.zone_a_text.pack(fill=tk.BOTH, expand=True)
        self.zone_a_text.insert("1.0", "Zone A: C=1, I=1 - 复杂问题拆解\n")
        
        # Zone B
        zone_b = ttk.Frame(zone_notebook, padding="10")
        zone_notebook.add(zone_b, text="Zone B (综合)")
        self.zone_b_text = scrolledtext.ScrolledText(zone_b, wrap=tk.WORD, font=('Consolas', 10))
        self.zone_b_text.pack(fill=tk.BOTH, expand=True)
        self.zone_b_text.insert("1.0", "Zone B: C=1, I=0 - 混合策略\n")
        
        # Zone C
        zone_c = ttk.Frame(zone_notebook, padding="10")
        zone_notebook.add(zone_c, text="Zone C (大脑/出口)")
        self.zone_c_text = scrolledtext.ScrolledText(zone_c, wrap=tk.WORD, font=('Consolas', 10))
        self.zone_c_text.pack(fill=tk.BOTH, expand=True)
        self.zone_c_text.insert("1.0", "Zone C: C=0, I=1 - 统一出口\n支持三种模式：直接/队列/组装\n")
        
        # Zone D
        zone_d = ttk.Frame(zone_notebook, padding="10")
        zone_notebook.add(zone_d, text="Zone D (补I)")
        self.zone_d_text = scrolledtext.ScrolledText(zone_d, wrap=tk.WORD, font=('Consolas', 10))
        self.zone_d_text.pack(fill=tk.BOTH, expand=True)
        self.zone_d_text.insert("1.0", "Zone D: C=0, I=0 - 信息检索\n")
        
    # ===== Execution Methods =====
    
    def on_enter_pressed(self, event):
        if not event.state & 0x1:
            self.execute_v4_pipeline()
            return 'break'
    
    def execute_v4_pipeline(self):
        """Execute V4 Pipeline"""
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("输入为空", "请输入查询语句")
            return
        
        if not V4_AVAILABLE or not self.v4_pipeline:
            messagebox.showerror("错误", "V4 Pipeline 不可用")
            return
        
        self.status_bar.config(text=f"执行 V4 Pipeline...")
        self.root.update()
        
        try:
            if self.level1_router is None and self.documents:
                self.level1_router = Level1Router(documents=self.documents)
            if self.level2_router is None:
                self.level2_router = Level2Router(use_dual_probe=False)
            
            self.v4_pipeline.l1_router = self.level1_router
            self.v4_pipeline.l2_router = self.level2_router
            
            result = self.v4_pipeline.process(query)
            
            self.update_v4_results(result)
            self.status_bar.config(text=f"完成 ({result.latency_ms:.2f}ms)")
            
        except Exception as e:
            import traceback
            messagebox.showerror("错误", f"执行失败:\n{str(e)}\n\n{traceback.format_exc()}")
            self.status_bar.config(text=f"错误")
    
    def execute_orchestrator_v4(self):
        """Execute V4 Orchestrator"""
        query = self.query_text.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("输入为空", "请输入查询语句")
            return
        
        if not V4_AVAILABLE or not self.orchestrator_v4:
            messagebox.showerror("错误", "V4 Orchestrator 不可用")
            return
        
        self.status_bar.config(text="执行 V4 Orchestrator...")
        self.root.update()
        
        try:
            ci_state = {'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3,
                       'sigma_c': 0.7, 'sigma_i': 0.6}
            result = self.orchestrator_v4.request_transition(query, ci_state, 'D', attempt_count=1)
            
            text = f"""=== V4 Orchestrator 转区请求 ===

查询: {query}
来源Zone: {result.source_zone.value}
当前CI: C={result.ci_state.C:.2f}, I={result.ci_state.I:.2f}

转区结果:
  成功: {result.success}
  动作: {result.action}
  目标Zone: {result.target_zone.value if result.target_zone else 'N/A'}
  触发策略升级: {result.trigger_strategy_upgrade}
  强制转区: {result.force_transition}

消息: {result.message}
"""
            self.orch_text.delete("1.0", tk.END)
            self.orch_text.insert("1.0", text)
            self.notebook.select(self.orch_frame)
            self.status_bar.config(text="V4 Orchestrator 完成")
            
        except Exception as e:
            messagebox.showerror("错误", f"执行失败: {e}")
            self.status_bar.config(text=f"错误")
    
    def update_v4_results(self, result):
        """Update UI with V4 results"""
        # Update summary
        self.c_label.config(text=f"{result.ci_state.get('C', '-')}")
        self.i_label.config(text=f"{result.ci_state.get('I', '-')}")
        
        zone = result.final_zone
        self.zone_label.config(text=f"Zone {zone}", foreground=self.get_zone_color(zone))
        
        ci = result.ci_state
        self.sigma_c_label.config(text=f"{ci.get('sigma_c', 0):.3f}")
        self.sigma_c_bar['value'] = ci.get('sigma_c', 0) * 100
        self.sigma_i_label.config(text=f"{ci.get('sigma_i', 0):.3f}")
        self.sigma_i_bar['value'] = ci.get('sigma_i', 0) * 100
        self.sigma_joint_label.config(text=f"{ci.get('sigma_joint', 0):.3f}")
        self.sigma_joint_bar['value'] = ci.get('sigma_joint', 0) * 100
        
        path = " -> ".join([s.get('step', '?') for s in result.execution_path[:4]])
        self.path_label.config(text=path + "..." if len(result.execution_path) > 4 else path)
        self.time_label.config(text=f"{result.latency_ms:.2f}ms")
        
        # Update V4 Pipeline tab with detailed execution info
        v4_text = f"""=== V4 Pipeline 执行结果 ===

查询: {result.query}
最终Zone: {result.final_zone}
耗时: {result.latency_ms:.2f}ms

=== 执行路径详解 ===
"""
        for i, step in enumerate(result.execution_path, 1):
            v4_text += f"\n{'='*50}\n"
            v4_text += f"步骤 {i}: {step.get('step', 'unknown')}\n"
            v4_text += f"{'='*50}\n"
            
            if 'zone' in step:
                v4_text += f"Zone: {step['zone']}\n"
            
            if 'ci' in step:
                ci = step['ci']
                v4_text += f"CI状态: C={ci.get('C', '?')} (复杂{'高' if ci.get('C')==1 else '低'}), "
                v4_text += f"I={ci.get('I', '?')} (信息{'足' if ci.get('I')==1 else '不足'})\n"
                v4_text += f"  连续值: C={ci.get('C_continuous', 0):.2f}, I={ci.get('I_continuous', 0):.2f}\n"
                v4_text += f"  置信度: σ_c={ci.get('sigma_c', 0):.2f}, σ_i={ci.get('sigma_i', 0):.2f}\n"
            
            # Show explanation
            if 'explanation' in step:
                v4_text += f"\n【执行说明】\n{step['explanation']}\n"
            
            # Show retrieval details
            if 'retrieved_details' in step and step['retrieved_details']:
                v4_text += f"\n【检索到的信息】(Top {len(step['retrieved_details'])}):\n"
                for doc in step['retrieved_details']:
                    v4_text += f"  [{doc['id']}] 分数:{doc['score']:.3f}\n"
                    v4_text += f"    内容: {doc['content']}\n"
            
            # Show sub-problem details
            if 'subproblems_details' in step and step['subproblems_details']:
                v4_text += f"\n【生成的子问题】({len(step['subproblems_details'])}个):\n"
                for sp in step['subproblems_details']:
                    simple_mark = "✓简" if sp.get('is_simple') else "✗复"
                    v4_text += f"  [{sp['id']}] {simple_mark}: {sp['query'][:80]}...\n"
            
            # Show orchestrator action
            if 'action' in step:
                v4_text += f"\n【协调器决策】\n"
                v4_text += f"  动作: {step['action']}\n"
                v4_text += f"  成功: {'是' if step.get('success') else '否'}\n"
                if step.get('target'):
                    v4_text += f"  目标Zone: {step['target']}\n"
                if step.get('upgrade_triggered'):
                    v4_text += f"  策略升级: 已触发\n"
        
        v4_text += f"\n{'='*50}\n"
        v4_text += f"=== 最终输出 ===\n{result.answer}\n"
        
        self.v4_text.delete("1.0", tk.END)
        self.v4_text.insert("1.0", v4_text)
        
        # Update Zone tabs with formatted detailed info
        for step in result.execution_path:
            zone = step.get('zone', '')
            
            # Build formatted text for zone tabs
            zone_text = f"=== Zone {zone} 执行详情 ===\n\n"
            
            if 'ci' in step:
                ci = step['ci']
                zone_text += f"【CI状态变化】\n"
                zone_text += f"  C (复杂度): {ci.get('C', '?')} ({'高' if ci.get('C')==1 else '低'})\n"
                zone_text += f"    连续值: {ci.get('C_continuous', 0):.3f}\n"
                zone_text += f"  I (信息度): {ci.get('I', '?')} ({'足' if ci.get('I')==1 else '不足'})\n"
                zone_text += f"    连续值: {ci.get('I_continuous', 0):.3f}\n"
                zone_text += f"  置信度: σ_c={ci.get('sigma_c', 0):.3f}, σ_i={ci.get('sigma_i', 0):.3f}\n\n"
            
            if 'explanation' in step:
                zone_text += f"【执行说明】\n{step['explanation']}\n\n"
            
            if 'retrieved_details' in step and step['retrieved_details']:
                zone_text += f"【检索结果】({len(step['retrieved_details'])}条):\n"
                for doc in step['retrieved_details']:
                    zone_text += f"\n  [{doc['id']}] 相关度: {doc['score']:.3f}\n"
                    zone_text += f"  内容: {doc['content']}\n"
                zone_text += "\n"
            
            if 'subproblems_details' in step and step['subproblems_details']:
                zone_text += f"【子问题列表】({len(step['subproblems_details'])}个):\n"
                for sp in step['subproblems_details']:
                    status = "✓ 已简化" if sp.get('is_simple') else "✗ 仍复杂"
                    zone_text += f"\n  [{sp['id']}] {status}\n"
                    zone_text += f"  查询: {sp['query']}\n"
                zone_text += "\n"
            
            if 'strategy' in step:
                zone_text += f"【使用策略】{step['strategy']}\n\n"
            
            # Update appropriate zone tab
            if zone == 'A':
                self.zone_a_text.delete("1.0", tk.END)
                self.zone_a_text.insert("1.0", zone_text)
            elif zone == 'B':
                self.zone_b_text.delete("1.0", tk.END)
                self.zone_b_text.insert("1.0", zone_text)
            elif zone == 'C':
                self.zone_c_text.delete("1.0", tk.END)
                self.zone_c_text.insert("1.0", zone_text)
            elif zone == 'D':
                self.zone_d_text.delete("1.0", tk.END)
                self.zone_d_text.insert("1.0", zone_text)
        
        # Update JSON
        self.json_text.delete("1.0", tk.END)
        self.json_text.insert("1.0", json.dumps({
            'query': result.query,
            'final_zone': result.final_zone,
            'ci_state': result.ci_state,
            'execution_path': result.execution_path,
            'latency_ms': result.latency_ms
        }, indent=2, ensure_ascii=False))
    
    def get_zone_color(self, zone):
        colors = {'A': 'purple', 'B': 'orange', 'C': 'green', 'D': 'blue'}
        return colors.get(zone, 'black')
    
    # ===== V4 Test Point Methods =====
    
    def test_ci_mapping(self):
        """Test CI to Zone mapping"""
        from ci_architecture.orchestrator.orchestrator_v4 import CIState
        
        test_cases = [
            (0.2, 0.8, 'C'), (0.2, 0.3, 'D'),
            (0.7, 0.3, 'B'), (0.7, 0.8, 'A'),
        ]
        
        results = []
        for C, I, expected in test_cases:
            ci = CIState(C=C, I=I, sigma_c=0.7, sigma_i=0.7)
            zone = ci.zone
            passed = zone.value == expected
            results.append(f"C={C}, I={I} -> Zone {zone.value} (expected {expected}) {'OK' if passed else 'FAIL'}")
        
        self.show_test_result("CI映射测试", "\n".join(results))
    
    def test_zone_d(self):
        """Test Zone D"""
        handler = ZoneDHandler()
        result = handler.enter('test query', {'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3})
        
        text = f"""Zone D (补I区) 测试结果:

检索文档数: {len(result.retrieved_info)}
新I值: {result.ci_state['I_continuous']:.3f}
策略: {result.strategy_used}
请求转区: {result.transition_requested}
"""
        self.show_test_result("Zone D测试", text)
    
    def test_zone_a(self):
        """Test Zone A"""
        handler = ZoneAHandler()
        result = handler.enter('complex problem', {'C': 1, 'I': 1, 'C_continuous': 0.8, 'I_continuous': 0.9})
        
        sub_text = "\n".join([f"  - [{sp['id']}] {sp['query'][:50]}..." for sp in result.sub_problems])
        text = f"""Zone A (拆解区) 测试结果:

子问题数量: {len(result.sub_problems)}
全部简单: {result.metadata.get('all_simple', False)}
策略: {result.strategy_used}

子问题:
{sub_text}
"""
        self.show_test_result("Zone A测试", text)
    
    def test_zone_b(self):
        """Test Zone B"""
        handler = ZoneBHandler()
        result = handler.enter('hybrid query', {'C': 1, 'I': 0, 'C_continuous': 0.7, 'I_continuous': 0.3})
        
        text = f"""Zone B (综合区) 测试结果:

策略: {result.strategy_used}
新C值: {result.ci_state['C']}
新I值: {result.ci_state['I_continuous']:.3f}
检索信息: {len(result.retrieved_info)} 条
子问题: {len(result.sub_problems)} 个
"""
        self.show_test_result("Zone B测试", text)
    
    def test_zone_c_direct(self):
        """Test Zone C direct mode"""
        handler = ZoneCHandler()
        result = handler.process_direct('What is Python?', strategy=ReasoningStrategy.DIRECT)
        
        text = f"""Zone C (大脑/出口) - 直接模式:

输出: {result.output}

策略: {result.strategy_used}
策略等级: {result.metadata.get('strategy_level', 1)}
CI: C={result.ci_state['C']}, I={result.ci_state['I']}
"""
        self.show_test_result("Zone C直接模式", text)
    
    def test_zone_c_queue(self):
        """Test Zone C queue mode"""
        queue = SubProblemQueue()
        handler = ZoneCHandler(subproblem_queue=queue)
        queue.register_parent('p1', ['sp1', 'sp2'])
        
        r1 = handler.process_subproblem('p1', 'sp1', 'What is ML?')
        r2 = handler.process_subproblem('p1', 'sp2', 'What is DL?')
        
        text = f"""Zone C (大脑/出口) - 队列模式:

父问题: p1
子问题数: 2

第1个: {r1.metadata.get('mode')}
第2个: {r2.metadata.get('mode')}

队列完成: {queue.is_complete('p1')}
组装输出: {r2.output if r2.output else 'N/A'}
"""
        self.show_test_result("Zone C队列模式", text)
    
    def test_strategy_upgrade(self):
        """Test strategy upgrade"""
        sm = StrategyManager()
        strategies = [sm.get_initial_strategy('D')]
        for _ in range(3):
            strategies.append(sm.upgrade_strategy('D', strategies[-1], 'test'))
        
        text = f"""策略升级测试 (Zone D):

升级链: {' -> '.join(strategies)}
最大尝试: {sm.max_attempts}
强制转区(3次): {sm.should_force_transition('D', 3)}
"""
        self.show_test_result("策略升级测试", text)
    
    def test_transition_validation(self):
        """Test transition validation"""
        orch = OrchestratorV4()
        
        scenarios = [
            ('D', 0.2, 0.8, True, 'C=0, I>=0.7 -> APPROVE'),
            ('D', 0.2, 0.5, False, 'C=0, I<0.7 -> REJECT'),
            ('A', 0.2, 0.8, True, 'A->C with good I'),
        ]
        
        results = []
        for source, C, I, expected, desc in scenarios:
            ci_state = {
                'C': 0 if C < 0.5 else 1, 'I': 1 if I >= 0.7 else 0,
                'C_continuous': C, 'I_continuous': I, 'sigma_c': 0.7, 'sigma_i': 0.8
            }
            result = orch.request_transition('test', ci_state, source)
            passed = result.success == expected
            status = "OK" if passed else "FAIL"
            results.append(f"{source}->C (C={C}, I={I}): {'APPROVED' if result.success else 'REJECTED'} [{status}] - {desc}")
        
        self.show_test_result("转区校验测试", "\n".join(results))
    
    def show_test_result(self, title, content):
        """Show test result popup"""
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("600x400")
        
        text = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert("1.0", content)
        
        ttk.Button(popup, text="关闭", command=popup.destroy).pack(pady=5)
    
    def show_examples(self):
        """Show example queries"""
        examples = [
            "什么是Python?",
            "分析微服务架构的性能优化方案",
            "患者咳嗽有铁锈色痰，胸痛发热",
            "设计一个支持百万并发的电商系统",
        ]
        
        menu = tk.Menu(self.root, tearoff=0)
        for ex in examples:
            menu.add_command(label=ex[:50], command=lambda q=ex: self.set_query(q))
        
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()
    
    def set_query(self, query):
        """Set query and execute"""
        self.query_text.delete("1.0", tk.END)
        self.query_text.insert("1.0", query)
        self.execute_v4_pipeline()
    
    def clear_input(self):
        """Clear input"""
        self.query_text.delete("1.0", tk.END)
        self.query_text.focus()
    
    def reload_routers(self):
        """Reload routers"""
        self.status_bar.config(text="重新加载...")
        self.root.update()
        self.level1_router = None
        self.level2_router = None
        self.init_routers()
        messagebox.showinfo("重新加载", "模型已重新加载")
        self.status_bar.config(text="就绪")
    
    def run(self):
        """Run the application"""
        self.root.mainloop()


def main():
    if not TKINTER_AVAILABLE:
        print("Error: tkinter is required.")
        sys.exit(1)
    
    app = CIRouterTestWindowV4()
    app.run()


if __name__ == '__main__':
    main()