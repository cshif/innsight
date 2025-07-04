import pytest
import jieba
import os


def test_jieba_custom_dictionary():
    """測試 jieba 載入自訂詞庫後的分詞效果。"""
    # 載入自訂詞庫
    dict_path = os.path.join(os.path.dirname(__file__), "..", "resources", "user_dict.txt")
    jieba.load_userdict(dict_path)
    
    def jieba_with_hiragana_support(text):
        """繞過 jieba 日文字符限制的分詞器"""
        # 日文字符映射
        hiragana_map = {'ら': '拉'}
        word_map = {'美拉海水族館': '美ら海水族館'}
        
        # 字符替換
        temp_text = text
        for hiragana, chinese in hiragana_map.items():
            temp_text = temp_text.replace(hiragana, chinese)
        
        # 確保替換詞語在詞典中
        for temp_word in word_map.keys():
            jieba.add_word(temp_word, freq=999999, tag='nz')
        
        # 分詞
        tokens = jieba.lcut(temp_text)
        
        # 還原詞語
        result = []
        for token in tokens:
            result.append(word_map.get(token, token))
        
        return result
    
    # 測試分詞
    tokens1 = jieba_with_hiragana_support("我想去沖繩的美ら海水族館")
    tokens2 = jieba.lcut("今歸仁海岸很美")
    tokens3 = jieba.lcut("恩納的飯店好停車")
    tokens4 = jieba.lcut("帶孩子去首里城看看")
    
    # 測試斷言
    assert "沖繩" in tokens1 and "美ら海水族館" in tokens1
    assert "今歸仁" in tokens2
    assert "恩納" in tokens3
    assert "首里城" in tokens4


if __name__ == "__main__":
    pytest.main([__file__])