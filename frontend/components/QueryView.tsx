'use client';

import React, { useState } from 'react';
import { Send, Loader } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { queryCodebase } from '../lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

// Custom components for ReactMarkdown
const MarkdownComponents = {
  // Code blocks with syntax highlighting
  code({ node, inline, className, children, ...props }: any) {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    
    if (!inline && (match || String(children).includes('\n'))) {
      return (
        <SyntaxHighlighter
          style={oneDark}
          language={language || 'text'}
          PreTag="div"
          className="rounded-md my-2 text-sm"
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      );
    }
    
    return (
      <code className="bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
        {children}
      </code>
    );
  },
  // Paragraphs
  p({ children }: any) {
    return <p className="mb-3 last:mb-0">{children}</p>;
  },
  // Headings
  h1({ children }: any) {
    return <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0">{children}</h1>;
  },
  h2({ children }: any) {
    return <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h2>;
  },
  h3({ children }: any) {
    return <h3 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h3>;
  },
  // Lists
  ul({ children }: any) {
    return <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>;
  },
  ol({ children }: any) {
    return <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>;
  },
  li({ children }: any) {
    return <li className="ml-2">{children}</li>;
  },
  // Bold and italic
  strong({ children }: any) {
    return <strong className="font-semibold">{children}</strong>;
  },
  em({ children }: any) {
    return <em className="italic">{children}</em>;
  },
  // Links
  a({ href, children }: any) {
    return (
      <a href={href} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
  // Blockquotes
  blockquote({ children }: any) {
    return (
      <blockquote className="border-l-4 border-gray-300 pl-4 italic my-3 text-gray-600">
        {children}
      </blockquote>
    );
  },
  // Tables
  table({ children }: any) {
    return (
      <div className="overflow-x-auto my-3">
        <table className="min-w-full border border-gray-300 rounded">{children}</table>
      </div>
    );
  },
  th({ children }: any) {
    return <th className="border border-gray-300 px-3 py-2 bg-gray-100 font-semibold text-left">{children}</th>;
  },
  td({ children }: any) {
    return <td className="border border-gray-300 px-3 py-2">{children}</td>;
  },
  // Horizontal rule
  hr() {
    return <hr className="my-4 border-gray-300" />;
  },
};

export default function QueryView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const result = await queryCodebase(input);
      const assistantMessage: Message = {
        role: 'assistant',
        content: result.answer,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${error.response?.data?.detail || 'Query failed'}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 h-screen flex flex-col">
      <h2 className="text-3xl font-bold mb-6 text-gray-800">Ask Questions</h2>

      {/* Messages */}
      <div className="flex-1 bg-white rounded-lg shadow-lg p-6 overflow-y-auto mb-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-20">
            <p className="text-lg mb-4">Ask questions about your codebase</p>
            <div className="text-sm space-y-2">
              <p>Example questions:</p>
              <ul className="list-disc list-inside">
                <li>What are the main functions in this codebase?</li>
                <li>How does the authentication work?</li>
                <li>Show me the database schema</li>
                <li>What APIs are exposed?</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-3xl px-4 py-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {msg.role === 'user' ? (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  ) : (
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={MarkdownComponents}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 px-4 py-3 rounded-lg">
                  <Loader className="animate-spin text-gray-600" size={20} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask a question about your code..."
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:bg-gray-400 flex items-center gap-2"
        >
          <Send size={20} />
        </button>
      </div>
    </div>
  );
}

