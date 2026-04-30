import json
import os
import sys
import logging

logger = logging.getLogger("AcidFootCongee.config")

class ConfigManager:
    """管理并加载 keys.json 配置文件"""
    
    def __init__(self, config_path=None):
        if config_path is None:
            # 默认配置路径：当前项目根目录下的 keys.json
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(base_dir, "keys.json")
        else:
            self.config_path = config_path
            
        self.config = None
        self.delays = {}
        
    def get_config_path(self):
        return self.config_path
        
    def load(self):
        """加载配置文件并解析"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            
        if 'keys' not in self.config or not isinstance(self.config['keys'], list):
            raise ValueError("配置文件格式错误: 'keys'字段不存在或格式不正确")
            
        self._parse_delays()
        return self.config['keys']
        
    def _parse_delays(self):
        """解析延迟配置"""
        default_delay_keys = [
            "window_focus", "mouse_move", "mouse_down", 
            "buy_button", "buy_complete", "esc_key", "loop_interval"
        ]
        
        delay_config = self.config.get('delays', {})
        for key in default_delay_keys:
            if key in delay_config:
                if isinstance(delay_config[key], dict) and 'value' in delay_config[key]:
                    self.delays[key] = delay_config[key]['value']
                elif isinstance(delay_config[key], (int, float)):
                    self.delays[key] = delay_config[key]
                else:
                    self.delays[key] = 0.01
            else:
                self.delays[key] = 0.01

    def update_position(self, key_name, new_position):
        """更新特定键的相对坐标并保存到文件"""
        if not self.config or 'keys' not in self.config:
            self.load()
            
        updated = False
        for item in self.config['keys']:
            if item.get('key_name') == key_name:
                item['position'] = new_position
                updated = True
                break
                
        if updated:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        return False

    def save(self, new_config):
        """保存配置到文件（带完整性校验）"""
        # 校验必要字段
        if not isinstance(new_config, dict):
            raise ValueError("配置数据必须是字典类型")
        if 'keys' in new_config and not isinstance(new_config['keys'], list):
            raise ValueError("'keys' 字段必须是列表类型")
        
        # 确保目标目录存在
        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        
        self.config = new_config
        logger.info(f"配置已保存到: {self.config_path}")
        return True
