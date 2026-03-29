import requests
import json
import time
import os
from bs4 import BeautifulSoup
import re


def load_case_links(filename='all_case_links.json'):
    """加载之前保存的病例链接"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            links = json.load(f)
        print(f"成功加载 {len(links)} 个病例链接")
        return links
    except FileNotFoundError:
        print(f"文件 {filename} 不存在，请先运行链接抓取程序")
        return []
    except json.JSONDecodeError:
        print(f"文件 {filename} 格式错误")
        return []


def load_progress(progress_file='progress.json'):
    """加载爬取进度"""
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
            print(f"从进度文件加载: 已处理 {progress.get('processed', 0)} 个链接")
            return progress
        except:
            pass
    return {'processed': 0, 'failed_urls': []}


def save_progress(progress, progress_file='progress.json'):
    """保存爬取进度"""
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存进度文件时出错: {e}")


def create_session():
    """创建带有请求头的会话"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    })
    return session


def extract_case_summary(case_summary_div):
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


def extract_case_section(case_section_div):
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


def extract_analysis_summary(case_analysis_div):
    """提取分析总结部分的内容"""
    analysis_text = case_analysis_div.get_text(strip=True)
    return analysis_text


def is_case_data_empty(case_data):
    """检查病例数据是否全部为空（除了URL字段）"""
    # 检查除了url以外的所有字段是否都为空
    fields_to_check = ["标题", "病例摘要", "病案介绍", "诊治过程", "分析总结"]

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


def parse_case_detail(session, case_url):
    """解析单个病例详情页"""
    case_data = {
        "标题": "",
        "病例摘要": "",
        "病案介绍": {},
        "诊治过程": {},
        "分析总结": "",
        "url": case_url
    }

    try:
        print(f"正在解析: {case_url}")

        # 发送请求
        response = session.get(case_url, timeout=15)
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

        # 2. 提取病例摘要
        case_summary_div = soup.find('div', class_='case_summary')
        if not case_summary_div:
            # 尝试查找包含position1的class
            case_summary_div = soup.find('div', class_=lambda x: x and 'case_summary' in x and 'position1' in x)

        if case_summary_div:
            case_data["病例摘要"] = extract_case_summary(case_summary_div)

        # 3. 提取病案介绍
        case_study_position2 = soup.find('div', class_='case_study')
        if not case_study_position2:
            # 尝试查找包含position2的class
            case_study_position2 = soup.find('div', class_=lambda x: x and 'case_study' in x and 'position2' in x)

        if case_study_position2:
            case_data["病案介绍"] = extract_case_section(case_study_position2)

        # 4. 提取诊治过程
        case_study_position3 = soup.find('div', class_='case_study')
        if not case_study_position3:
            # 尝试查找包含position3的class
            case_study_position3 = soup.find('div', class_=lambda x: x and 'case_study' in x and 'position3' in x)

        if case_study_position3:
            # 需要区分position3和position2
            all_case_study = soup.find_all('div', class_=lambda x: x and 'case_study' in x)
            for div in all_case_study:
                if 'position3' in div.get('class', []):
                    case_data["诊治过程"] = extract_case_section(div)
                    break

        # 5. 提取分析总结
        case_study_position4 = soup.find('div', class_='case_study position4')
        if case_study_position4:
            # 查找position4下的div
            inner_div = case_study_position4.find('div')
            if inner_div:
                case_data["分析总结"] = extract_analysis_summary(inner_div)
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


def save_single_case_data(case_data, filename='case_details.json'):
    """保存单条病例数据到JSON文件（追加模式）"""
    try:
        # 检查文件是否存在
        file_exists = os.path.exists(filename)

        # 读取现有数据或创建新列表
        if file_exists and os.path.getsize(filename) > 0:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
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
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        return True
    except IOError as e:
        print(f"保存文件时出错: {e}")
        return False
    except Exception as e:
        print(f"处理数据时出错: {e}")
        return False


def main():
    # 1. 加载病例链接
    case_links = load_case_links()
    if not case_links:
        print("没有找到病例链接，程序退出")
        return

    # 2. 加载进度
    progress = load_progress()
    processed_count = progress.get('processed', 0)
    failed_urls = progress.get('failed_urls', [])

    print(f"从第 {processed_count + 1} 个链接开始处理")

    # 3. 创建会话
    session = create_session()

    # 4. 解析病例详情
    all_case_data = []

    print("\n开始解析病例详情...")
    print("=" * 60)

    try:
        for i, url in enumerate(case_links[processed_count:], start=processed_count):
            print(f"\n[{i + 1}/{len(case_links)}]")

            # 解析单个病例
            case_data = parse_case_detail(session, url)

            if case_data:
                # 检查数据是否全部为空
                if is_case_data_empty(case_data):
                    print(f"\n⚠️ 警告: 第 {i + 1} 个URL解析结果全部为空!")
                    print(f"异常URL: {url}")
                    print("程序暂停，请检查该URL对应的页面结构...")

                    # 保存进度
                    progress['failed_urls'] = failed_urls
                    save_progress(progress)

                    # 询问用户是否继续
                    user_input = input("是否跳过此URL继续处理下一个? (y/n): ").strip().lower()
                    if user_input == 'y' or user_input == 'yes':
                        failed_urls.append(url)
                        progress['processed'] = i
                        save_progress(progress)
                        print("跳过此URL，继续处理下一个...")
                        continue
                    else:
                        print("程序停止。")
                        break

                # 保存单条数据
                if save_single_case_data(case_data):
                    print(f"  已保存到本地文件")
                    all_case_data.append(case_data)
                    progress['processed'] = i + 1
                    save_progress(progress)
                else:
                    print(f"  保存失败")
                    failed_urls.append(url)
            else:
                print(f"  解析失败")
                failed_urls.append(url)

                # 保存进度
                progress['failed_urls'] = failed_urls
                save_progress(progress)

                # 询问是否继续
                print(f"\n⚠️ 第 {i + 1} 个URL解析失败!")
                print(f"异常URL: {url}")
                user_input = input("是否跳过此URL继续处理下一个? (y/n): ").strip().lower()
                if user_input == 'y' or user_input == 'yes':
                    print("跳过此URL，继续处理下一个...")
                    progress['processed'] = i + 1
                    save_progress(progress)
                    continue
                else:
                    print("程序停止。")
                    break

            # 礼貌性延迟，避免请求过快
            time.sleep(1.5)

            # 每10个病例显示一次进度
            if (i + 1) % 10 == 0:
                print(f"\n进度: 已解析 {i + 1}/{len(case_links)} 个病例")
                print(f"成功: {len(all_case_data)}, 失败: {len(failed_urls)}")
                print(f"当前进度已保存")

    except KeyboardInterrupt:
        print("\n\n用户中断程序，保存当前进度...")
        progress['processed'] = i
        save_progress(progress)
    except Exception as e:
        print(f"\n程序发生异常: {e}")
        print(f"异常发生在第 {i + 1} 个URL: {url}")
        progress['processed'] = i
        save_progress(progress)

    # 5. 显示统计信息
    print("\n" + "=" * 60)
    print("解析完成或中断!")
    print(f"成功解析: {len(all_case_data)} 个病例")
    print(f"解析失败: {len(failed_urls)} 个病例")
    print(f"进度已保存，下次将从第 {progress.get('processed', 0) + 1} 个链接开始")

    if failed_urls:
        print("\n失败的URL列表:")
        for idx, failed_url in enumerate(failed_urls[:10], 1):
            print(f"  {idx}. {failed_url}")
        if len(failed_urls) > 10:
            print(f"  还有 {len(failed_urls) - 10} 个失败的URL...")

        # 保存失败URL列表到文件
        try:
            with open('failed_urls.json', 'w', encoding='utf-8') as f:
                json.dump(failed_urls, f, ensure_ascii=False, indent=2)
            print(f"失败URL列表已保存到 failed_urls.json")
        except:
            pass

    # 6. 显示第一个病例的数据结构作为示例（如果有数据）
    if all_case_data:
        print("\n最后一个成功解析的病例数据结构示例:")
        last_case = all_case_data[-1]
        for key, value in last_case.items():
            if key == "url":
                print(f"  {key}: {value}")
            elif isinstance(value, dict):
                print(f"  {key}: 字典，包含 {len(value)} 个键")
                for sub_key in list(value.keys())[:3]:  # 显示前3个子键
                    sub_value = value[sub_key]
                    preview = str(sub_value)[:50] + "..." if len(str(sub_value)) > 50 else str(sub_value)
                    print(f"    - {sub_key}: {preview}")
            else:
                preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                print(f"  {key}: {preview}")
    else:
        print("未能解析任何病例数据")

    # 7. 关闭会话
    session.close()


if __name__ == "__main__":
    main()