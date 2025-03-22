
import requests
import json
import time

class MailTM:
    def __init__(self):
        self.base_url = "https://api.mail.tm"
        self.token = None
        self.email = None
        self.password = None

    def create_account(self):
        # 获取可用域名列表
        domains_response = requests.get(f"{self.base_url}/domains")
        domains = domains_response.json()["hydra:member"]
        if not domains:
            raise Exception("No available domains")
        
        # 使用第一个可用域名
        domain = domains[0]["domain"]
        
        # 生成随机邮箱和密码
        import random
        import string
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"{username}@{domain}"
        self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        # 创建账号
        response = requests.post(
            f"{self.base_url}/accounts",
            json={"address": self.email, "password": self.password}
        )
        
        if response.status_code != 201:
            raise Exception(f"Failed to create account: {response.text}")
        
        # 获取token
        self._get_token()
        return self.email

    def _get_token(self):
        response = requests.post(
            f"{self.base_url}/token",
            json={"address": self.email, "password": self.password}
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get token: {response.text}")
        
        self.token = response.json()["token"]

    def wait_for_verification_code(self, timeout=180, check_interval=3, max_retries=3):
        if not self.token:
            raise Exception("Not authenticated")
        
        headers = {"Authorization": f"Bearer {self.token}"}
        start_time = time.time()
        retries = 0
        last_message_count = 0
        
        while retries < max_retries:
            try:
                while time.time() - start_time < timeout:
                    # 获取邮件列表
                    response = requests.get(
                        f"{self.base_url}/messages",
                        headers=headers,
                        timeout=10
                    )
                    
                    if response.status_code != 200:
                        print(f"获取邮件列表失败: {response.text}")
                        time.sleep(check_interval)
                        continue
                    
                    messages = response.json()["hydra:member"]
                    current_message_count = len(messages)
                    
                    if current_message_count > last_message_count:
                        print(f"检测到新邮件，当前邮箱中有 {current_message_count} 封邮件")
                        last_message_count = current_message_count
                        
                        # 立即处理新邮件，优先处理最新的邮件
                        for message in reversed(messages):
                            subject = message.get("subject", "")
                            print(f"检查邮件主题: {subject}")
                            if "账户验证通知" in subject:
                                print(f"找到验证邮件，ID: {message['id']}，正在获取详情...")
                                # 获取邮件详情
                                message_id = message["id"]
                                retry_count = 0
                                max_retries = 3
                                
                                while retry_count < max_retries:
                                    try:
                                        message_response = requests.get(
                                            f"{self.base_url}/messages/{message_id}",
                                            headers=headers,
                                            timeout=10
                                        )
                                        
                                        if message_response.status_code == 200:
                                            message_detail = message_response.json()
                                            text = message_detail.get("text", "")
                                            html = message_detail.get("html", "")
                                            
                                            # 优先从HTML内容中提取验证码
                                            content_to_check = html if html else text
                                            print(f"邮件内容类型: {'HTML' if html else 'Text'}")
                                            print(f"邮件内容长度: {len(content_to_check)} 字符")
                                            
                                            # 使用更精确的正则表达式匹配验证码
                                            import re
                                            # 尝试多种验证码格式匹配
                                            patterns = [
                                                r'验证码[：:]*\s*(\d{6})',  # 中文冒号格式
                                                r'verification code[：:]*\s*(\d{6})',  # 英文格式
                                                r'code[：:]*\s*(\d{6})',  # 简短英文格式
                                                r'[^\d](\d{6})[^\d]'  # 上下文隔离的6位数字
                                            ]
                                            
                                            for pattern in patterns:
                                                print(f"尝试匹配模式: {pattern}")
                                                try:
                                                    code_match = re.search(pattern, str(content_to_check), re.IGNORECASE)
                                                    if code_match:
                                                        verification_code = code_match.group(1) if len(code_match.groups()) > 0 else code_match.group(0)
                                                        print(f"成功获取到验证码: {verification_code}，匹配模式: {pattern}")
                                                        return verification_code
                                                except TypeError as e:
                                                    print(f"匹配验证码时发生类型错误: {str(e)}，内容类型: {type(content_to_check)}")
                                                    continue
                                            
                                            print("尝试所有匹配模式后未找到验证码")
                                            break  # 如果内容获取成功但未找到验证码，跳出重试循环
                                        else:
                                            print(f"获取邮件详情失败: HTTP {message_response.status_code}")
                                            print(f"错误信息: {message_response.text}")
                                            retry_count += 1
                                            if retry_count < max_retries:
                                                print(f"正在进行第 {retry_count + 1} 次重试...")
                                                time.sleep(2)  # 重试前等待2秒
                                            
                                    except requests.exceptions.RequestException as e:
                                        print(f"请求邮件详情时发生错误: {str(e)}")
                                        retry_count += 1
                                        if retry_count < max_retries:
                                            print(f"正在进行第 {retry_count + 1} 次重试...")
                                            time.sleep(2)  # 重试前等待2秒
                                        continue
                    
                    elapsed_time = int(time.time() - start_time)
                    remaining_time = timeout - elapsed_time
                    print(f"等待新邮件中... 已等待 {elapsed_time} 秒，剩余 {remaining_time} 秒")
                
                print(f"第 {retries + 1} 次尝试超时，正在重试...")
                retries += 1
                start_time = time.time()
                last_message_count = 0
                
            except requests.exceptions.RequestException as e:
                print(f"网络请求异常: {str(e)}，5秒后重试")
                retries += 1
                time.sleep(5)
                continue
        
        raise Exception(f"验证码获取失败，已重试 {max_retries} 次，总等待时间 {int(time.time() - start_time)} 秒")
