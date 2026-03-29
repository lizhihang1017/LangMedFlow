import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urlparse, urljoin
import os

class DetailPageCrawler:
    def __init__(self, start_url, post_url_pattern, save_path, max_pages=20):
        """
        初始化爬虫
        :param start_url: 起始URL（第一页）
        :param post_url_pattern: 后续分页的POST请求URL模式，使用 {} 占位符，例如 "https://bingli.iiyi.com/cull/{}.html"
        :param save_path: 结果保存的文件路径
        :param max_pages: 最大抓取页数
        """
        self.start_url = start_url
        self.post_url_pattern = post_url_pattern
        self.save_path = save_path
        self.max_pages = max_pages
        
        # 解析域名信息用于构建Header
        parsed_url = urlparse(start_url)
        self.domain = parsed_url.netloc
        self.base_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        self.session = self._create_session()

    def _create_session(self):
        """创建带有完整请求头的会话"""
        session = requests.Session()

        # 动态构建请求头
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Host': self.domain,
            'Origin': self.base_origin,
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })

        return session

    def extract_links_from_html(self, html_content):
        """从HTML中提取详情页链接"""
        links = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 方法1: 直接查找所有class="name"的a标签 (通用性较强的一种常见模式)
            for a_tag in soup.find_all('a', class_='name'):
                if a_tag and a_tag.has_attr('href'):
                    href = a_tag['href'].strip()
                    full_url = urljoin(self.base_origin, href)
                    links.append(full_url)

            # 方法2: 如果没找到，尝试通过容器查找 (针对特定站点结构)
            if not links:
                case_container = soup.find('div', class_='case_database_box')
                if case_container:
                    for li_div in case_container.find_all('div', class_='li'):
                        a_tag = li_div.find('a', class_='name')
                        if a_tag and a_tag.has_attr('href'):
                            href = a_tag['href'].strip()
                            full_url = urljoin(self.base_origin, href)
                            links.append(full_url)
                            
        except Exception as e:
            print(f"解析HTML提取链接时出错: {e}")

        return links

    def get_links_from_page(self, page_url, page_number, referer_url):
        """
        向指定的分页URL发送请求，并提取该页的链接
        """
        try:
            print(f"正在抓取第 {page_number} 页: {page_url}")

            # 更新Referer头
            self.session.headers.update({'Referer': referer_url})

            # 第一页用GET，后续分页用POST (根据需求描述)
            if page_number == 1:
                response = self.session.get(page_url, timeout=15)
                response.encoding = 'utf-8'
                html_content = response.text
                
                # 保存Cookie用于后续请求
                if 'Set-Cookie' in response.headers:
                    print("已获取Cookie")
            else:
                # POST请求，设置Content-Type
                self.session.headers.update({
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Content-Length': '0'
                })

                response = self.session.post(page_url, timeout=15)
                response.encoding = 'utf-8'

                # 尝试解析为JSON
                try:
                    if response.text.strip():
                        json_data = response.json()
                        # 从JSON中提取HTML片段
                        if isinstance(json_data, dict) and 'data' in json_data and 'html' in json_data['data']:
                            html_content = json_data['data']['html']
                        elif isinstance(json_data, dict) and 'html' in json_data:
                            html_content = json_data['html']
                        else:
                            # 可能是直接返回了HTML或者其他结构
                            html_content = str(json_data)
                    else:
                        print("响应为空")
                        return None
                except json.JSONDecodeError:
                    # 如果不是JSON，可能是HTML
                    html_content = response.text

            # 提取链接
            page_links = self.extract_links_from_html(html_content)

            if page_links:
                print(f"  第 {page_number} 页成功提取到 {len(page_links)} 个链接。")
                return page_links
            else:
                print(f"  第 {page_number} 页未提取到链接。")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  请求第 {page_number} 页时出错: {e}")
            return None
        except Exception as e:
            print(f"  处理第 {page_number} 页时发生意外错误: {e}")
            return None

    def save_results(self, links):
        """保存结果到文件"""
        try:
            # 确保目录存在
            directory = os.path.dirname(self.save_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            with open(self.save_path, 'w', encoding='utf-8') as f:
                json.dump(links, f, ensure_ascii=False, indent=4)
            print(f"所有链接已保存到文件: {self.save_path}")
            return True
        except IOError as e:
            print(f"保存文件时出错: {e}")
            return False

    def run(self):
        """
        执行爬虫主逻辑
        """
        all_links = []

        # 1. 抓取第一页
        print("=" * 50)
        print("开始抓取起始页...")
        first_page_links = self.get_links_from_page(self.start_url, 1, self.start_url)
        if first_page_links:
            all_links.extend(first_page_links)
            print(f"起始页抓取成功，获得 {len(first_page_links)} 个链接。")
        else:
            print("起始页抓取失败，程序终止。")
            return []

        # 2. 抓取后续分页
        print("\n" + "=" * 50)
        print("开始抓取后续分页...")
        
        for page_num in range(2, self.max_pages + 1):
            # 使用提供的模式构建URL
            try:
                page_url = self.post_url_pattern.format(page_num)
            except Exception as e:
                print(f"URL模式格式化失败: {e}")
                break

            # 设置Referer
            if page_num == 2:
                referer = self.start_url
            else:
                referer = self.post_url_pattern.format(page_num - 1)

            page_links = self.get_links_from_page(page_url, page_num, referer)

            # 判断是否继续
            if page_links is None:
                print(f"第 {page_num} 页抓取失败，尝试下一页...")
                time.sleep(2)
                continue
            elif len(page_links) == 0:
                print(f"第 {page_num} 页无链接，停止抓取。")
                break
            else:
                all_links.extend(page_links)

            # 随机延迟
            delay = 1.5 + (page_num % 3) * 0.5
            time.sleep(delay)
            
            if page_num % 5 == 0:
                print(f"已抓取 {page_num} 页，累计 {len(all_links)} 个链接...")

        # 3. 去重
        unique_links = []
        seen = set()
        for link in all_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        print("=" * 50)
        print(f"所有页面抓取完成！")
        print(f"原始链接数: {len(all_links)}")
        print(f"去重后链接数: {len(unique_links)}")
        
        self.session.close()
        
        # 保存结果
        if unique_links:
            self.save_results(unique_links)
            
        return unique_links

if __name__ == "__main__":
    # ================= 配置区域 =================
    # 1. 基础网址 (第一页)
    BASE_URL = "https://bingli.iiyi.com/dept/56-1.html"
    
    # 2. POST请求的基础网址模式 (使用 {} 作为页码占位符)
    POST_URL_PATTERN = "https://bingli.iiyi.com/dept/56-{}.html"
    
    # 3. 保存文件路径
    SAVE_FILE_PATH = os.path.join(os.getcwd(), "output", "gu_links.json")
    
    # 4. 最大抓取页数
    MAX_PAGES = 10
    # ===========================================

    print(f"配置信息:")
    print(f"起始URL: {BASE_URL}")
    print(f"POST模式: {POST_URL_PATTERN}")
    print(f"保存路径: {SAVE_FILE_PATH}")
    print("-" * 30)

    crawler = DetailPageCrawler(BASE_URL, POST_URL_PATTERN, SAVE_FILE_PATH, MAX_PAGES)
    crawler.run()
