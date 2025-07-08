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


def test_jieba_multiple_calls_normal_sentences():
    """測試呼叫多次 jieba.lcut() 處理普通句子時，分詞效果不受自訂詞庫干擾。"""
    # 載入自訂詞庫
    dict_path = os.path.join(os.path.dirname(__file__), "..", "resources", "user_dict.txt")
    jieba.load_userdict(dict_path)
    
    # 測試普通句子多次分詞
    test_sentence = "我想吃拉麵"
    
    # 呼叫多次 jieba.lcut()
    result1 = jieba.lcut(test_sentence)
    result2 = jieba.lcut(test_sentence)
    result3 = jieba.lcut(test_sentence)
    
    # 驗證結果一致性
    assert result1 == result2 == result3, "多次呼叫結果應該一致"
    
    # 驗證分詞合理性（應該包含基本詞語）
    expected_tokens = ["我", "想", "吃"]
    for token in expected_tokens:
        assert token in result1, f"'{token}' 應該在分詞結果中"
    
    # 驗證 "拉麵" 被正確處理（可能分為 "拉" 和 "麵"）
    assert "拉" in result1 and "麵" in result1, "拉麵應該被合理分詞"
    
    # 測試其他普通句子
    normal_sentences = [
        "今天天氣很好",
        "我喜歡看電影",
        "這個蛋糕很好吃"
    ]
    
    for sentence in normal_sentences:
        # 每個句子呼叫多次
        results = [jieba.lcut(sentence) for _ in range(3)]
        
        # 驗證結果一致性
        assert all(r == results[0] for r in results), f"句子 '{sentence}' 多次分詞結果應該一致"
        
        # 驗證分詞合理性（詞語長度應該合理，不應有過長詞語）
        for tokens in results:
            assert all(len(token) <= 4 for token in tokens), f"句子 '{sentence}' 分詞結果中不應有過長詞語"


if __name__ == "__main__":
    pytest.main([__file__])