# -*- coding: utf-8 -*-
"""
Tushare Token 配置文件
"""
from dotenv import load_dotenv
from pathlib import Path
import os
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")

