from typing import List, Tuple, Dict, Any

from app.core.event import eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

from threading import Thread
import urllib.parse, requests, re, os, time
from webdav3.client import Client
from webdav3.exceptions import *

class xiaoyadownloader(_PluginBase):
    # 插件名称
    plugin_name = "小雅下载器"
    # 插件描述
    plugin_desc = "从小雅中下载文件或者文件夹"
    # 插件图标
    plugin_icon = "https://s2.loli.net/2023/04/24/Z9bMjB3TutzKDGY.png"
    # 插件版本
    plugin_version = "0.5"
    # 插件作者
    plugin_author = "neao"
    # 作者主页
    author_url = "https://github.com/neao-anderson"
    # 插件配置项ID前缀
    plugin_config_prefix = "xiaoyadownloader_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _urls = []
    _save_root = './'
    _options = {}
    _enabled = False
    

    def init_plugin(self, config: dict = None):
        # 读取配置
        logger.debug(f"[XIAOYA]开始初始化")
        if config:
            self._enabled = config.get("enabled")
            self._save_root = config.get("save_root")
            self._urls = config.get("urls")

            # 还需要读取webdav配置
            
            if isinstance(self._urls, str):
                self._urls = str(self._urls).split('\n')
            
            if self._enabled and self._urls:
                # 排除空的url
                new_urls = []
                for url in self._urls:
                    if url and url != '\n':
                        # 对URL进行解码
                        url = urllib.parse.unquote(url)
                        new_urls.append(url.replace("\n", ""))
                        logger.debug(f"[XIAOYA]解码后的URL:{str(url)}")
                self._urls = new_urls

                # 进行下载
                if self._enabled:
                    self._save_root = "/media/Downloads/"
                    error_flag, error_urls = self.xiaoya_downloaders(self._urls)
                    # 只执行一次
                    self._enabled = self._enabled and not error_flag

                # 更新错误urls
                self.update_config({
                    "enabled": self._enabled,
                    "save_root": self._save_root,
                    "urls": '\n'.join(self._urls),
                    "err_urls": '\n'.join(error_urls)
                })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
                   {
                       'component': 'VForm',
                       'content': [
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VSwitch',
                                               'props': {
                                                   'model': 'enabled',
                                                   'label': '启动下载',
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'save_root',
                                                   'label': '保存路径',
                                                   ':value': '/media/',
                                                   'rows': 1,
                                                   'placeholder': '请输入保存路径',
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'urls',
                                                   'label': '小雅URL',
                                                   'rows': 10,
                                                   'placeholder': '每行一个URL'
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextarea',
                                               'props': {
                                                   'model': 'err_urls',
                                                   'readonly': True,
                                                   'label': '错误url',
                                                   'rows': 2,
                                                   'placeholder': '错误的url配置会展示在此处，请修改上方url重新提交（错误的url不会下载）'
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                       },
                                       'content': [
                                           {
                                               'component': 'VAlert',
                                               'props': {
                                                   'type': 'info',
                                                   'variant': 'tonal',
                                                   'text': 'URL直接从地址栏复制或者右键复制下载链接'
                                                           '（小雅使用默认的账户密码（guest/guest_Api789））'
                                               }
                                           }
                                       ]
                                   }
                               ]
                           }
                       ]
                   }
               ], {
                   "enabled": False,
                   "save_root": "",
                   "urls": "",
                   "err_urls": ""
               }

    def get_page(self) -> List[dict]:
        pass

    def parse_url(self, url):
        logger.debug(f"[XIAOYA]开始解析url")
        # 根据URL解析主机
        pattern = r'^(?:http[s]?://)?([^:/\s]+)(?::(\d+))?'
        match = re.search(pattern, url)
        host = match.group(0)
        logger.debug(f"[XIAOYA]主机:{str(host)}")

        # 根据URL解析资源路径
        remote_path = url.replace(host,'')
        if remote_path.startswith('/d'):
            remote_path = remote_path[2:]
        remote_path = "/dav" + remote_path
        logger.debug(f"[XIAOYA]远程路径:{str(remote_path)}")
        
        # 设置保存文件夹
        save_floder = os.path.basename(url) # 最后一级目录
        logger.debug(f"[XIAOYA]保存文件夹:{str(save_floder)}")
        
        return {"remote_path": remote_path, "save_floder": save_floder}

    def list_remote(self, client, remote_path):
        logger.debug(f"[XIAOYA]开始获取资源列表")
        # 获取资源列表
        try:
            items = client.list(remote_path,get_info=True)
        except Exception as e:
            logger.error(f"[XIAOYA]获取远程文件列表时出错: {str(e)}")
        
        file_list = []
        
        for item in items:
            if item['isdir']: # 如果是文件夹，继续打开
                file_list += self.list_remote(client, item['path'])
            else: #对于文件直接进行下载
                _file_name, _ext = os.path.splitext(item['path'])
                file_list.append({
                    "name": item['name'],
                    "size": item['size'],
                    "remote_path": item['path'],
                    "file_type": _ext[1:],
                })
        return file_list 

    def download_file(self, item, retries=5, delay=3):
        logger.debug(f"[XIAOYA]开始下载单个文件")
        file_name   = item['name']
        file_size   = int(item['size'])
        remote_path = item['remote_path']
        save_path   = item["save_path"]

        if retries <= 0:
            logger.error(f"[XIAOYA]{str(file_name)}下载失败:")
            return 0

        if os.path.exists(save_path):
            _file_size = os.path.getsize(save_path)
            write_mode = 'ab'
            logger.info(f"[XIAOYA]开始续传文件{str(file_name)}")
        else:
            _file_size = 0
            write_mode = 'wb'
            logger.info(f"[XIAOYA]开始下载文件{str(file_name)}")

        try:
            headers = {'Range': 'bytes=%d-' % _file_size}
            with requests.get(self._options['webdav_hostname'] + remote_path, stream=True, auth=(self._options['webdav_login'], self._options['webdav_password']), headers=headers) as r:
                with open(save_path, write_mode) as f:
                    next_level = max(1, int(_file_size/file_size*10))*10
                    for chunk in r.iter_content(chunk_size = 1024*32 ):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                            _file_size += len(chunk)
                            progress = round(_file_size/file_size*100,2)
                            if progress >= next_level and file_size/(1024*1024*1024) > 1:
                                next_level += 10
                                logger.info(f"[XIAOYA]文件 {str(file_name)} 下载进度: {str(progress)}%,{str(round(_file_size/(1024*1024*1024),2))}GB/{str(round(file_size/(1024*1024*1024),2))}GB")
            logger.info(f"[XIAOYA]文件已从 {str(remote_path)} 下载到 {str(save_path)}")
            return 1
        except requests.exceptions.RequestException as e:
            # 捕获所有requests库的异常
            logger.error(f"[XIAOYA]出现下载异常: {e}")
            time.sleep(delay)
            return self.download_file(item, retries-1, delay*2)
        except IOError as e:
            # 捕获文件操作相关的异常
            logger.error(f"[XIAOYA]出现读写异常: {e}")
        except Exception as e:
            # 捕获其他未知异常
            logger.error(f"[XIAOYA]出现未知异常: {e}")

    def download_files(self, download_file_list):
        logger.debug(f"[XIAOYA]开始下载多个文件")
        total_file_num  = len(download_file_list)
        finish_file_num = 0
        # socketio.emit('update_list_progress', {'total_file_num': total_file_num, 'finish_file_num': finish_file_num})
        logger.info(f"总共需要下载{str(total_file_num)}个文件,已经下载{str(finish_file_num)}个文件")
        
        for item in download_file_list:
            file_name   = item['name']
            file_size   = int(item['size'])
            remote_path = item['remote_path']
            save_path   = item["save_path"]

            floder_path = os.path.dirname(save_path)
            if not os.path.exists(floder_path):
                os.makedirs(floder_path)

            if not os.path.exists(save_path) or os.path.getsize(save_path) < file_size:
                finish_file_num += self.download_file(item)
            else:
                finish_file_num += 1
                logger.warn(f"[XIAOYA]文件已存在")
            
            # socketio.emit('update_list_progress', {'total_file_num': total_file_num, 'finish_file_num': finish_file_num})
            logger.info(f"[XIAOYA]总共需要下载{str(total_file_num)}个文件,已经下载{str(finish_file_num)}个文件")
        
        logger.info(f"[XIAOYA]文件全部下载任务完成")

    def xiaoya_downloader(self, url, save_path):
        logger.debug(f"[XIAOYA]开始处理单个url")
        temp = self.parse_url(url)
        url = temp["url"]
        host = temp["host"]
        remote_path = temp["remote_path"]
        save_floder = temp["save_floder"]
        
        # WebDAV 连接配置
        self._options = {
            'webdav_hostname': host,
            'webdav_login':    "guest",
            'webdav_password': "guest_Api789",
            'disable_check': True,
        }
        # 创建客户端实例
        client = Client(self._options)
        
        download_file_list = []

        #此处可以设置筛选规则
        item = ''
        try:
            item = client.info(remote_path)
        except Exception as e:
            logger.error(f"[XIAOYA]获取文件信息时出错: {str(e)}")
        
        # 判断是文件还是文件夹
        if item["size"]:
            _file_name, _ext = os.path.splitext(save_floder)
            download_file_list=[{
                    "name": item['name'],
                    "size": item['size'],
                    "remote_path": remote_path,
                    "file_type": _ext[1:],
                    'save_path': save_path + save_floder
                }]
        else:
            download_file_list = self.list_remote(client, remote_path)
            for item in download_file_list:
                item["save_path"] =  item["remote_path"].replace(remote_path,save_path+save_floder)

        self.download_files(download_file_list)
        # self.systemmessage.put(f"[XIYA] {str(err)}下载完成")

    def xiaoya_downloaders(self, urls):
        """
        逐一下载每个URL
        """
        logger.debug(f"[XIAOYA]开始处理多个url")
        if not _save_root.endswith('/'):
            _save_root = _save_root + '/'
        
        err_urls = ["111","https://111.bbb.com"]
        err_flag = True
        for index, url in enumerate(urls):
            try:
                self.xiaoya_downloader(self, url, _save_root)
            except Exception as e:
                err_urls.append(url + "\n")
                logger.error(f"[XIAOYA] {str(e)}下载失败")
                # 推送实时消息
                # self.systemmessage.put(f"[XIAOYA]{str(e)}下载失败")
        return err_flag, err_urls

    def stop_service(self):
        """
        退出插件
        """
        pass

    @eventmanager.register(EventType.PluginReload)
    def reload(self, event):
        """
        响应插件重载事件
        """
        plugin_id = event.event_data.get("plugin_id")
        if not plugin_id:
            return
        if plugin_id != self.__class__.__name__:
            return
        return self.init_plugin(self.get_config())
