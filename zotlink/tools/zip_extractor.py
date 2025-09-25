#!/usr/bin/env python3
"""
ZIP PDF提取器
从ZIP文件中自动提取PDF文件，支持Word文档转PDF
"""

import io
import zipfile
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class ZipPDFExtractor:
    """ZIP PDF提取器"""
    
    def __init__(self):
        self.supported_pdf_extensions = ['.pdf', '.PDF']
        self.max_file_size = 100 * 1024 * 1024  # 100MB
    
    def extract_pdf_from_zip(self, zip_data: bytes, source_url: str = "") -> Optional[Dict]:
        """
        从ZIP文件中提取PDF或转换Word文档
        
        Args:
            zip_data: ZIP文件的二进制数据
            source_url: 来源URL（用于日志）
            
        Returns:
            包含PDF数据和元数据的字典，如果失败返回None
        """
        try:
            if not self._is_zip_data(zip_data):
                logger.warning("提供的数据不是有效的ZIP文件")
                return None
            
            logger.info(f"📦 开始处理ZIP文件 ({len(zip_data)} bytes)")
            
            # 使用BytesIO创建文件对象
            zip_buffer = io.BytesIO(zip_data)
            
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                # 获取ZIP文件信息
                file_list = zip_file.namelist()
                logger.info(f"📂 ZIP文件包含 {len(file_list)} 个文件")
                
                # 🚀 新增：检查是否为Word文档格式并转换为PDF
                if self._is_word_document(file_list):
                    logger.info("🔍 检测到Word文档格式（.docx）")
                    
                    # 🚀 关键改进：尝试将Word文档转换为PDF
                    try:
                        from .pdf_converter import convert_word_data_to_pdf
                        
                        logger.info("📄 尝试将Word文档转换为PDF以优化Zotero兼容性...")
                        conversion_result = convert_word_data_to_pdf(zip_data, "PsyArXiv-Paper")
                        
                        if conversion_result["success"]:
                            # 转换成功，返回PDF数据
                            result = {
                                'pdf_data': conversion_result["pdf_data"],
                                'filename': 'PsyArXiv-Paper.pdf',
                                'size': conversion_result["pdf_size"],
                                'extracted_from': f"Word文档转换为PDF (来源: {source_url})",
                                'format': 'PDF',
                                'original_path': 'PsyArXiv-Paper.pdf',
                                'zip_file_count': len(file_list),
                                'conversion_details': {
                                    'original_format': 'DOCX',
                                    'original_size': conversion_result["original_size"],
                                    'converted_size': conversion_result["pdf_size"]
                                }
                            }
                            
                            logger.info(f"🎉 Word文档成功转换为PDF!")
                            logger.info(f"   📄 原格式: Microsoft Word文档")
                            logger.info(f"   🔄 新格式: PDF文档")
                            logger.info(f"   📦 原大小: {conversion_result['original_size']/1024:.1f} KB")
                            logger.info(f"   📦 PDF大小: {conversion_result['pdf_size']/1024:.1f} KB")
                            logger.info(f"   ✅ Zotero兼容性: 完美")
                            
                            return result
                            
                        else:
                            # 转换失败，fallback到Word文档
                            logger.warning(f"⚠️ PDF转换失败: {conversion_result['message']}")
                            logger.info("📄 回退到Word文档格式")
                            
                            # 检查是否需要安装指南
                            fallback_result = {
                                'pdf_data': zip_data,
                                'filename': 'document.docx',
                                'size': len(zip_data),
                                'extracted_from': f"Word文档 (PDF转换失败, 来源: {source_url})",
                                'format': 'DOCX',
                                'original_path': 'document.docx',
                                'zip_file_count': len(file_list),
                                'conversion_error': conversion_result['message']
                            }
                            
                            if conversion_result.get("installation_guide"):
                                fallback_result['installation_guide'] = conversion_result["installation_guide"]
                            
                            logger.info(f"📄 Word文档作为备选方案")
                            logger.info(f"   📦 大小: {len(zip_data)/1024:.1f} KB")
                            logger.info(f"   ⚠️ Zotero兼容性: 有限")
                            
                            return fallback_result
                            
                    except ImportError as e:
                        logger.warning(f"⚠️ PDF转换器模块不可用: {e}")
                        # Fallback到原始Word文档处理
                        pass
                    except Exception as e:
                        logger.error(f"❌ PDF转换异常: {e}")
                        # Fallback到原始Word文档处理
                        pass
                    
                    # 🔙 Fallback: 原始Word文档处理
                    result = {
                        'pdf_data': zip_data,
                        'filename': 'document.docx',
                        'size': len(zip_data),
                        'extracted_from': f"Word文档 (来源: {source_url})",
                        'format': 'DOCX',
                        'original_path': 'document.docx',
                        'zip_file_count': len(file_list)
                    }
                    
                    logger.info(f"✅ Word文档处理完成 (未转换)")
                    logger.info(f"   📄 格式: Microsoft Word文档")
                    logger.info(f"   📦 大小: {result['size']} bytes ({result['size']/1024:.1f} KB)")
                    logger.info(f"   🗂️ 内含文件: {len(file_list)} 个")
                    
                    return result
                
                # 查找PDF文件
                pdf_files = self._find_pdf_files(file_list)
                
                if not pdf_files:
                    logger.warning("❌ ZIP文件中未找到PDF文件")
                    logger.info(f"📋 文件列表: {file_list[:10]}{'...' if len(file_list) > 10 else ''}")
                    return None
                
                logger.info(f"📄 找到 {len(pdf_files)} 个PDF文件")
                
                # 按优先级排序PDF文件
                pdf_files.sort(key=self._get_pdf_priority, reverse=True)
                
                # 提取第一个（最高优先级的）PDF文件
                target_pdf = pdf_files[0]
                logger.info(f"🎯 选择PDF文件: {target_pdf}")
                
                # 读取PDF文件内容
                with zip_file.open(target_pdf) as pdf_file:
                    pdf_data = pdf_file.read()
                
                if not self._is_pdf_data(pdf_data):
                    logger.error(f"❌ 提取的文件不是有效PDF: {target_pdf}")
                    return None
                
                result = {
                    'pdf_data': pdf_data,
                    'filename': target_pdf.split('/')[-1],  # 只取文件名
                    'size': len(pdf_data),
                    'extracted_from': f"ZIP文件 (来源: {source_url})",
                    'format': 'PDF',
                    'original_path': target_pdf,
                    'zip_file_count': len(file_list)
                }
                
                logger.info(f"✅ PDF提取成功!")
                logger.info(f"   📄 文件名: {result['filename']}")
                logger.info(f"   📦 大小: {result['size']} bytes ({result['size']/1024:.1f} KB)")
                logger.info(f"   🗂️ ZIP中文件数: {len(file_list)}")
                
                return result
                
        except zipfile.BadZipFile as e:
            logger.error(f"❌ 无效的ZIP文件: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 处理ZIP文件时发生错误: {e}")
            return None
    
    def _is_zip_data(self, data: bytes) -> bool:
        """检查数据是否为ZIP格式"""
        return data.startswith(b'PK\x03\x04') or data.startswith(b'PK\x05\x06') or data.startswith(b'PK\x07\x08')
    
    def _is_pdf_data(self, data: bytes) -> bool:
        """检查数据是否为PDF格式"""
        return data.startswith(b'%PDF')
    
    def _is_word_document(self, file_list: List[str]) -> bool:
        """
        检查ZIP文件是否为Word文档格式
        """
        word_indicators = [
            '[Content_Types].xml',
            'word/document.xml',
            '_rels/.rels'
        ]
        
        for indicator in word_indicators:
            if indicator not in file_list:
                return False
        
        # 检查是否有足够的word/目录下的文件
        word_files = [f for f in file_list if f.startswith('word/') and f.endswith('.xml')]
        return len(word_files) >= 3
    
    def _find_pdf_files(self, file_list: List[str]) -> List[str]:
        """从文件列表中找到PDF文件"""
        pdf_files = []
        for filename in file_list:
            if any(filename.lower().endswith(ext.lower()) for ext in self.supported_pdf_extensions):
                pdf_files.append(filename)
        return pdf_files
    
    def _get_pdf_priority(self, pdf_filename: str) -> int:
        """
        给PDF文件设置优先级，数值越高优先级越高
        
        优先级规则：
        1. 主文件（不在子文件夹中）优先级最高
        2. 文件名包含"main", "paper", "article"等关键词的优先级高
        3. 文件名不包含"supplement", "appendix", "SI"等的优先级高
        """
        priority = 0
        filename_lower = pdf_filename.lower()
        
        # 主文件夹中的文件优先级高
        if '/' not in pdf_filename:
            priority += 100
        
        # 文件名关键词加分
        main_keywords = ['main', 'paper', 'article', 'manuscript', 'full']
        for keyword in main_keywords:
            if keyword in filename_lower:
                priority += 50
                break
        
        # 补充材料关键词减分
        supplement_keywords = ['supplement', 'appendix', 'si', 'supporting', 'additional']
        for keyword in supplement_keywords:
            if keyword in filename_lower:
                priority -= 50
                break
        
        return priority
    
    def analyze_zip_structure(self, zip_data: bytes) -> Dict:
        """分析ZIP文件结构"""
        try:
            zip_buffer = io.BytesIO(zip_data)
            structure = {
                'total_files': 0,
                'pdf_files': [],
                'other_files': [],
                'is_word_document': False,
                'file_types': {}
            }
            
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                file_list = zip_file.namelist()
                structure['total_files'] = len(file_list)
                structure['is_word_document'] = self._is_word_document(file_list)
                
                for filename in file_list:
                    ext = filename.split('.')[-1].lower() if '.' in filename else 'no_ext'
                    structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                    
                    if any(filename.lower().endswith(pdf_ext.lower()) for pdf_ext in self.supported_pdf_extensions):
                        structure['pdf_files'].append(filename)
                    else:
                        structure['other_files'].append(filename)
            
            return structure
            
        except Exception as e:
            return {'error': str(e)} 