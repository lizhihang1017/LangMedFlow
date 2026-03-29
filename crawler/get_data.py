import requests
import json
import time
import os
from bs4 import BeautifulSoup
import re

class CaseDataCrawler:
    def __init__(self, links_file, data_file, progress_file, interactive=True):
        """
        初始化爬虫
        :param links_file: 包含链接列表的JSON文件路径
        :param data_file: 保存结果的JSON文件路径
        :param progress_file: 保存进度的JSON文件路径
        :param interactive: 是否在出错时交互式询问 (True/False)
        """
        self.links_file = links_file
        self.data_file = data_file
        self.progress_file = progress_file
        self.interactive = interactive
        self.session = self._create_session()

    def _create_session(self):
        """创建带有请求头的会话"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        })
        return session

    def load_case_links(self):
        """加载之前保存的病例链接"""
        try:
            with open(self.links_file, 'r', encoding='utf-8') as f:
                links = json.load(f)
            print(f"成功加载 {len(links)} 个病例链接")
            return links
        except FileNotFoundError:
            print(f"文件 {self.links_file} 不存在，请先运行链接抓取程序")
            return []
        except json.JSONDecodeError:
            print(f"文件 {self.links_file} 格式错误")
            return []

    def load_progress(self):
        """加载爬取进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                print(f"从进度文件加载: 已处理 {progress.get('processed', 0)} 个链接")
                return progress
            except:
                pass
        return {'processed': 0, 'failed_urls': []}

    def save_progress(self, progress):
        """保存爬取进度"""
        try:
            # 确保目录存在
            directory = os.path.dirname(self.progress_file)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存进度文件时出错: {e}")

    def extract_case_summary(self, case_summary_div):
        """提取病例摘要信息"""
        case_summary_text = ""

        if case_summary_div:
            # 查找所有p标签
            p_tags = case_summary_div.find_all('p')
            for p in p_tags:
                var_tag = p.find('var')
                span_tag = p.find('span')

                if var_tag and span_tag:
                    # 提取var和span的内容
                    var_text = var_tag.get_text(strip=True)
                    span_text = span_tag.get_text(strip=True)
                    case_summary_text += f"{var_text} {span_text}\n"
                elif var_tag:
                    # 只有var标签
                    var_text = var_tag.get_text(strip=True)
                    case_summary_text += f"{var_text}\n"
                elif span_tag:
                    # 只有span标签
                    span_text = span_tag.get_text(strip=True)
                    case_summary_text += f"{span_text}\n"
                else:
                    # 没有var和span，直接获取p标签文本
                    p_text = p.get_text(strip=True)
                    if p_text:
                        case_summary_text += f"{p_text}\n"

        return case_summary_text.strip()

    def extract_case_section(self, case_section_div):
        """提取病案介绍、诊治过程等部分的内容，返回字典格式"""
        section_dict = {}

        if not case_section_div:
            return section_dict

        # 找到所有子div，每个子div包含一个h3和内容
        child_divs = case_section_div.find_all('div', recursive=False)

        for child_div in child_divs:
            # 查找h3标签
            h3_tag = child_div.find('h3')
            if h3_tag:
                # 查找em标签获取小标题
                em_tag = h3_tag.find('em')
                if em_tag:
                    section_title = em_tag.get_text(strip=True)
                else:
                    # 如果没有em标签，使用整个h3的文本
                    section_title = h3_tag.get_text(strip=True)
                    # 清理标题中的数字和标点
                    section_title = re.sub(r'^\d+\.', '', section_title).strip()

                # 提取内容：h3之后的所有文本
                content_parts = []

                # 先获取h3之后的所有兄弟节点
                for sibling in h3_tag.next_siblings:
                    if sibling.name == 'br':
                        content_parts.append('\n')
                    elif sibling.name == 'p':
                        # 如果是p标签，递归获取其所有文本
                        p_text = sibling.get_text(strip=False)
                        content_parts.append(p_text)
                    elif sibling.name == 'div':
                        # 如果是div标签，获取其所有文本
                        div_text = sibling.get_text(strip=False)
                        content_parts.append(div_text)
                    elif isinstance(sibling, str):
                        # 如果是纯文本
                        text = sibling.strip()
                        if text:
                            content_parts.append(text)
                    elif sibling.name == 'img':
                        # 如果是图片，记录图片URL
                        img_src = sibling.get('src', '')
                        if img_src:
                            content_parts.append(f"[图片: {img_src}]")

                # 如果没有通过兄弟节点找到内容，尝试获取整个div的文本并去掉h3部分
                if not content_parts:
                    full_text = child_div.get_text(strip=False)
                    h3_text = h3_tag.get_text(strip=False)
                    content = full_text.replace(h3_text, '', 1).strip()
                    if content:
                        content_parts.append(content)

                # 合并内容
                content = ''.join(content_parts).strip()

                # 清理内容中的多余空白字符
                content = re.sub(r'\s+', ' ', content)

                if section_title and content:
                    section_dict[section_title] = content

        # 如果通过子div没有找到内容，尝试直接提取文本
        if not section_dict:
            # 先移除h2标题
            h2_tag = case_section_div.find('h2')
            if h2_tag:
                h2_text = h2_tag.get_text(strip=False)
                full_text = case_section_div.get_text(strip=False)
                content = full_text.replace(h2_text, '', 1).strip()
                if content:
                    section_dict["内容"] = content

        return section_dict

    def extract_analysis_summary(self, case_analysis_div):
        """提取分析总结部分的内容"""
        analysis_text = case_analysis_div.get_text(strip=True)
        return analysis_text

    def extract_department(self, soup):
        """提取科室信息"""
        department = ""
        breadcrumbs = soup.find('div', class_='breadcrumbs')
        if breadcrumbs:
            a_tags = breadcrumbs.find_all('a')
            # 过滤掉第一个（首页）和最后一个（当前文章标题）
            dept_list = []
            for i, a in enumerate(a_tags):
                # 跳过第一个 "爱爱医病例中心"
                if i == 0:
                    continue
                
                # 如果是最后一个，通常是标题，跳过
                if i == len(a_tags) - 1:
                    continue
                    
                text = a.get_text(strip=True)
                if text:
                    dept_list.append(text)
            
            if dept_list:
                department = "/".join(dept_list)
                
        return department

    def is_case_data_empty(self, case_data):
        """检查病例数据是否全部为空（除了URL字段）"""
        # 检查除了url以外的所有字段是否都为空
        fields_to_check = ["标题", "科室", "病例摘要", "病案介绍", "诊治过程", "分析总结"]

        for field in fields_to_check:
            if field == "病案介绍" or field == "诊治过程":
                # 如果是字典类型，检查是否为空
                if case_data.get(field):
                    return False
            else:
                # 如果是字符串类型，检查是否有内容
                if case_data.get(field, "").strip():
                    return False

        return True

    def parse_case_detail(self, case_url):
        """解析单个病例详情页"""
        case_data = {
            "标题": "",
            "科室": "",
            "病例摘要": "",
            "病案介绍": {},
            "诊治过程": {},
            "分析总结": "",
            "url": case_url
        }

        try:
            print(f"正在解析: {case_url}")

            # 发送请求
            response = self.session.get(case_url, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"  请求失败，状态码: {response.status_code}")
                return None

            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. 提取标题
            case_details_cont = soup.find('div', class_='case_details_cont')
            if case_details_cont:
                h2_tag = case_details_cont.find('h2')
                if h2_tag:
                    case_data["标题"] = h2_tag.get_text(strip=True)

            # 2. 提取科室
            case_data["科室"] = self.extract_department(soup)

            # 3. 提取病例摘要
            case_summary_div = soup.find('div', class_='case_summary')
            if not case_summary_div:
                # 尝试查找包含position1的class
                case_summary_div = soup.find('div', class_=lambda x: x and 'case_summary' in x and 'position1' in x)

            if case_summary_div:
                case_data["病例摘要"] = self.extract_case_summary(case_summary_div)

            # 4. 提取病案介绍
            case_study_position2 = soup.find('div', class_='case_study')
            if not case_study_position2:
                # 尝试查找包含position2的class
                case_study_position2 = soup.find('div', class_=lambda x: x and 'case_study' in x and 'position2' in x)

            if case_study_position2:
                case_data["病案介绍"] = self.extract_case_section(case_study_position2)

            # 5. 提取诊治过程
            case_study_position3 = soup.find('div', class_='case_study')
            if not case_study_position3:
                # 尝试查找包含position3的class
                case_study_position3 = soup.find('div', class_=lambda x: x and 'case_study' in x and 'position3' in x)

            if case_study_position3:
                # 需要区分position3和position2
                all_case_study = soup.find_all('div', class_=lambda x: x and 'case_study' in x)
                for div in all_case_study:
                    if 'position3' in div.get('class', []):
                        case_data["诊治过程"] = self.extract_case_section(div)
                        break

            # 6. 提取分析总结
            case_study_position4 = soup.find('div', class_='case_study position4')
            if case_study_position4:
                # 查找position4下的div
                inner_div = case_study_position4.find('div')
                if inner_div:
                    case_data["分析总结"] = self.extract_analysis_summary(inner_div)
                else:
                    # 如果没有找到内部div，直接使用position4的文本
                    case_data["分析总结"] = case_study_position4.get_text(strip=True)
                    # 移除"【分析总结】"标题
                    case_data["分析总结"] = case_data["分析总结"].replace("【分析总结】", "", 1).strip()

            # 检查是否成功提取到标题
            if not case_data["标题"]:
                print(f"  警告: 未提取到标题")

            print(f"  成功提取数据: 标题='{case_data['标题'][:30]}...'")
            return case_data

        except requests.exceptions.RequestException as e:
            print(f"  请求出错: {e}")
            return None
        except Exception as e:
            print(f"  解析出错: {e}")
            return None

    def save_single_case_data(self, case_data):
        """保存单条病例数据到JSON文件（追加模式）"""
        try:
            # 确保目录存在
            directory = os.path.dirname(self.data_file)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # 检查文件是否存在
            file_exists = os.path.exists(self.data_file)

            # 读取现有数据或创建新列表
            if file_exists and os.path.getsize(self.data_file) > 0:
                try:
                    with open(self.data_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                except:
                    existing_data = []
            else:
                existing_data = []

            # 添加新数据
            existing_data.append(case_data)

            # 保存数据
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            return True
        except IOError as e:
            print(f"保存文件时出错: {e}")
            return False
        except Exception as e:
            print(f"处理数据时出错: {e}")
            return False

    def run(self):
        # 1. 加载病例链接
        case_links = self.load_case_links()
        if not case_links:
            print("没有找到病例链接，程序退出")
            return

        # 2. 加载进度
        progress = self.load_progress()
        processed_count = progress.get('processed', 0)
        failed_urls = progress.get('failed_urls', [])

        print(f"从第 {processed_count + 1} 个链接开始处理")

        # 3. 开始解析
        all_case_data = []

        print("\n开始解析病例详情...")
        print("=" * 60)

        try:
            for i, url in enumerate(case_links[processed_count:], start=processed_count):
                print(f"\n[{i + 1}/{len(case_links)}]")

                # 解析单个病例
                case_data = self.parse_case_detail(url)

                if case_data:
                    # 检查数据是否全部为空
                    if self.is_case_data_empty(case_data):
                        print(f"\n⚠️ 警告: 第 {i + 1} 个URL解析结果全部为空!")
                        print(f"异常URL: {url}")
                        
                        # 保存进度
                        progress['failed_urls'] = failed_urls
                        self.save_progress(progress)

                        # 交互式处理
                        should_continue = True
                        if self.interactive:
                            user_input = input("是否跳过此URL继续处理下一个? (y/n): ").strip().lower()
                            if not (user_input == 'y' or user_input == 'yes'):
                                should_continue = False
                        else:
                            print("非交互模式：自动跳过此URL，继续处理下一个...")
                        
                        if should_continue:
                            failed_urls.append(url)
                            progress['processed'] = i
                            self.save_progress(progress)
                            continue
                        else:
                            print("程序停止。")
                            break

                    # 保存单条数据
                    if self.save_single_case_data(case_data):
                        print(f"  已保存到本地文件")
                        all_case_data.append(case_data)
                        progress['processed'] = i + 1
                        self.save_progress(progress)
                    else:
                        print(f"  保存失败")
                        failed_urls.append(url)
                else:
                    print(f"  解析失败")
                    failed_urls.append(url)

                    # 保存进度
                    progress['failed_urls'] = failed_urls
                    self.save_progress(progress)

                    # 交互式处理
                    should_continue = True
                    print(f"\n⚠️ 第 {i + 1} 个URL解析失败!")
                    print(f"异常URL: {url}")
                    
                    if self.interactive:
                        user_input = input("是否跳过此URL继续处理下一个? (y/n): ").strip().lower()
                        if not (user_input == 'y' or user_input == 'yes'):
                            should_continue = False
                    else:
                        print("非交互模式：自动跳过此URL，继续处理下一个...")
                    
                    if should_continue:
                        continue
                    else:
                        break

                # 随机延迟
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n用户手动停止程序")
        except Exception as e:
            print(f"\n发生未知错误: {e}")

        print("\n" + "=" * 60)
        print("程序运行结束")

if __name__ == "__main__":
    # ================= 配置区域 =================
    # 1. 包含链接的输入文件
    LINKS_FILE = os.path.join(os.getcwd(), "output", "gu_links.json")
    
    # 2. 详情数据输出文件
    DATA_OUTPUT_FILE = os.path.join(os.getcwd(), "output_data", "gu_details_data.json")
    
    # 3. 进度记录文件
    PROGRESS_FILE = os.path.join(os.getcwd(), "output_data", "gu_progress.json")
    
    # 4. 是否开启交互模式 (出错时询问)
    INTERACTIVE_MODE = True
    # ===========================================
    
    print(f"配置信息:")
    print(f"输入链接文件: {LINKS_FILE}")
    print(f"输出数据文件: {DATA_OUTPUT_FILE}")
    print(f"进度记录文件: {PROGRESS_FILE}")
    print("-" * 30)
    
    crawler = CaseDataCrawler(LINKS_FILE, DATA_OUTPUT_FILE, PROGRESS_FILE, INTERACTIVE_MODE)
    crawler.run()
