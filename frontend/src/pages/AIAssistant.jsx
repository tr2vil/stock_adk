import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Loader2, ExternalLink, Newspaper, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import axios from 'axios';
import styles from './AIAssistant.module.css';

const AIAssistant = () => {
    const [messages, setMessages] = useState([
        { role: 'assistant', type: 'text', content: '안녕하세요! 어떤 종목이 궁금하신가요? 뉴스 요약이나 분석을 도와드릴 수 있습니다.' }
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', type: 'text', content: userMessage }]);
        setIsLoading(true);

        try {
            const response = await axios.post('http://localhost:8000/api/chat', { message: userMessage });
            const data = response.data;

            if (data.type === 'A2UI_CARD' && data.agent === 'NewsAnalysis') {
                setMessages(prev => [...prev, { role: 'assistant', type: 'news_card', data: data.data, stock: data.stock }]);
            } else {
                setMessages(prev => [...prev, { role: 'assistant', type: 'text', content: data.message || '죄송합니다. 이해하지 못했습니다.' }]);
            }
        } catch (error) {
            setMessages(prev => [...prev, { role: 'assistant', type: 'text', content: '서버와 통신 중 오류가 발생했습니다.' }]);
        } finally {
            setIsLoading(false);
        }
    };

    const NewsCard = ({ data, stock }) => (
        <div className={styles.newsCard}>
            <div className={styles.cardHeader}>
                <Newspaper size={20} className="me-2 text-primary" />
                <h5 className="mb-0">{stock} 뉴스 요약</h5>
                <span className={`ms-auto badge ${data.sentiment === '긍정' ? 'bg-success' : data.sentiment === '부정' ? 'bg-danger' : 'bg-secondary'}`}>
                    {data.sentiment === '긍정' ? <TrendingUp size={14} className="me-1" /> :
                        data.sentiment === '부정' ? <TrendingDown size={14} className="me-1" /> :
                            <Minus size={14} className="me-1" />}
                    {data.sentiment}
                </span>
            </div>
            <div className={styles.cardBody}>
                <p className={styles.summary}>{data.summary}</p>
                <div className={styles.importantNews}>
                    <h6><TrendingUp size={16} className="me-1 text-warning" /> 주요 뉴스</h6>
                    {data.important_news.map((news, idx) => (
                        <div key={idx} className={styles.newsItem}>
                            <strong>{news.title}</strong>
                            <p className="small text-muted mb-0">{news.reason}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );

    return (
        <div className={styles.chatContainer}>
            <div className={styles.chatHeader}>
                <Bot className="me-2" /> AI 투자 비서
            </div>
            <div className={styles.messageList}>
                {messages.map((msg, idx) => (
                    <div key={idx} className={`${styles.messageWrapper} ${msg.role === 'user' ? styles.userRow : styles.assistantRow}`}>
                        <div className={styles.avatar}>
                            {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                        </div>
                        <div className={styles.messageContent}>
                            {msg.type === 'text' ? (
                                <div className={styles.textBubble}>{msg.content}</div>
                            ) : (
                                <NewsCard data={msg.data} stock={msg.stock} />
                            )}
                        </div>
                    </div>
                ))}
                {isLoading && (
                    <div className={styles.assistantRow}>
                        <div className={styles.avatar}><Bot size={16} /></div>
                        <div className={styles.loadingBubble}>
                            <Loader2 size={16} className="spinner" /> 생각 중...
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
            <form onSubmit={handleSend} className={styles.inputArea}>
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="종목 뉴스 요약해줘 (예: 삼성전자 뉴스 요약)"
                    className="form-control"
                />
                <button type="submit" className="btn btn-primary ms-2" disabled={isLoading}>
                    <Send size={18} />
                </button>
            </form>
        </div>
    );
};

export default AIAssistant;
