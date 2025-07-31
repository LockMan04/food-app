import { useState, useRef, useEffect } from 'react';
import { Upload, Send, Loader2, ChefHat, X, Edit3, Check, ChevronDown, ChevronUp, Clock, HelpCircle, Users, Flame } from 'lucide-react';
import './App.css';

const FoodDetectionApp = () => {
  const [uploadedImages, setUploadedImages] = useState([]);
  const [allDetectedIngredients, setAllDetectedIngredients] = useState([]);
  const [currentRecipe, setCurrentRecipe] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [editingIngredients, setEditingIngredients] = useState(false);
  const [tempIngredients, setTempIngredients] = useState([]);
  const [showChat, setShowChat] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // Fixed common questions - không cần gọi API
  const commonQuestions = [
    {
      text: "Thời gian nấu bao lâu?",
      question: "Thời gian nấu món này mất bao lâu?",
      category: "time",
      icon: Clock
    },
    {
      text: "Dùng lửa to hay nhỏ?",
      question: "Nên dùng lửa to hay lửa nhỏ khi nấu?",
      category: "technique",
      icon: Flame
    },
    {
      text: "Đủ cho mấy người?",
      question: "Công thức này đủ cho bao nhiêu người ăn?",
      category: "portion",
      icon: Users
    },
    {
      text: "Có mẹo gì đặc biệt?",
      question: "Có mẹo nào để món ăn ngon hơn không?",
      category: "tips",
      icon: HelpCircle
    }
  ];

  // Scroll to bottom when chatMessages change
  useEffect(() => {
    if (chatEndRef.current && showChat) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, showChat]);

  // Start chat session when recipe is ready
  useEffect(() => {
    if (currentRecipe && allDetectedIngredients.length && !sessionId) {
      startChatSession();
    }
  }, [currentRecipe, allDetectedIngredients]);

  // YOLO detection
  const detectIngredients = async (imageFile) => {
    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      
      const response = await fetch('http://localhost:5000/detect', {
        method: 'POST', 
        body: formData
      });
      
      const data = await response.json();
      
      if (data.success && data.ingredients) {
        return data.ingredients;
      } else {
        console.error('Detection failed:', data.error);
        return [];
      }
    } catch (error) {
      console.error('Error in detectIngredients:', error);
      return [];
    }
  };

  // Recipe generation
  const generateRecipe = async (ingredients) => {
    try {
      const response = await fetch('http://localhost:5000/generate-recipe', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ingredients})
      });
      
      const data = await response.json();
      
      if (data.success && data.recipe) {
        return data.recipe;
      } else {
        throw new Error(data.error || 'Failed to generate recipe');
      }
    } catch (error) {
      console.error('Error in generateRecipe:', error);
      throw error;
    }
  };

  // Start chat session with context
  const startChatSession = async () => {
    if (!currentRecipe || !allDetectedIngredients.length) return;

    try {
      const response = await fetch('http://localhost:5000/start-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ingredients: allDetectedIngredients,
          recipe: currentRecipe
        })
      });
      
      const data = await response.json();
      
      if (data.success && data.session_id) {
        setSessionId(data.session_id);
        console.log('✅ Chat session started:', data.session_id);
      } else {
        console.error('Failed to start chat session:', data.error);
      }
    } catch (error) {
      console.error('Error starting chat session:', error);
    }
  };

  // Stream chat with context memory
  const streamChatResponse = async (question) => {
    if (!sessionId || !question.trim()) return;

    const userMessage = {
      type: 'user',
      content: question,
      timestamp: new Date()
    };
    
    setChatMessages(prev => [...prev, userMessage]);
    
    // Add empty bot message for streaming
    const botMessageIndex = chatMessages.length + 1;
    setChatMessages(prev => [...prev, {
      type: 'bot',
      content: '',
      timestamp: new Date(),
      isComplete: false
    }]);
    
    setIsStreaming(true);
    
    try {
      const response = await fetch('http://localhost:5000/chat-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          question: question
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to start streaming');
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Process complete lines
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6); // Remove 'data: '
              const data = JSON.parse(jsonStr);
              
              if (data.type === 'chunk' && data.content) {
                // Update the bot message with new chunk
                setChatMessages(prev => prev.map((msg, idx) => 
                  idx === botMessageIndex
                    ? { ...msg, content: msg.content + data.content }
                    : msg
                ));
              } else if (data.type === 'done') {
                // Mark message as complete
                setChatMessages(prev => prev.map((msg, idx) => 
                  idx === botMessageIndex
                    ? { ...msg, isComplete: true }
                    : msg
                ));
                setIsStreaming(false);
                return;
              } else if (data.type === 'error') {
                throw new Error(data.error);
              }
            } catch (parseError) {
              console.error('Failed to parse streaming data:', parseError);
            }
          }
        }
        
        // Keep the last incomplete line in buffer
        buffer = lines[lines.length - 1];
      }
      
    } catch (error) {
      console.error('Streaming error:', error);
      
      // Update with error message
      setChatMessages(prev => prev.map((msg, idx) => 
        idx === botMessageIndex
          ? { 
              ...msg, 
              content: `Có lỗi khi kết nối server: ${error.message}`, 
              isComplete: true,
              isError: true 
            }
          : msg
      ));
      setIsStreaming(false);
    }
  };

  // Handle image upload
  const handleImageUpload = async (files) => {
    const fileList = Array.from(files);
    
    for (const file of fileList) {
      if (!file.type.startsWith('image/')) continue;
      
      const reader = new FileReader();
      reader.onload = async (e) => {
        const imageUrl = e.target.result;
        const imageId = Date.now() + Math.random();
        
        const newImage = {
          id: imageId,
          url: imageUrl,
          name: file.name,
          detecting: true,
          ingredients: []
        };
        
        setUploadedImages(prev => [...prev, newImage]);
        
        // Simulate processing delay then detect
        setTimeout(async () => {
          try {
            const detected = await detectIngredients(file);

            setUploadedImages(prev => prev.map(img =>
              img.id === imageId
                ? { ...img, detecting: false, ingredients: detected }
                : img
            ));
            
            setAllDetectedIngredients(prev => {
              const combined = [...prev, ...detected];
              return [...new Set(combined)];
            });
          } catch (error) {
            console.error('Detection error:', error);
            setUploadedImages(prev => prev.map(img =>
              img.id === imageId
                ? { ...img, detecting: false, ingredients: [] }
                : img
            ));
          }
        }, 1500);
      };
      
      reader.readAsDataURL(file);
    }
  };

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleImageUpload(files);
    }
  };

  const handleRemoveImage = (imageId) => {
    setUploadedImages(prev => {
      const newImages = prev.filter(img => img.id !== imageId);
      // Cập nhật lại allDetectedIngredients dựa trên các hình còn lại
      const allIngredients = newImages.flatMap(img => img.ingredients || []);
      setAllDetectedIngredients([...new Set(allIngredients)]);
      return newImages;
    });
  };

  const handleGenerateRecipe = async () => {
    if (allDetectedIngredients.length === 0) return;

    setIsProcessing(true);
    
    // End existing session if any
    if (sessionId) {
      try {
        await fetch(`http://localhost:5000/end-chat/${sessionId}`, {
          method: 'DELETE'
        });
      } catch (error) {
        console.error('Error ending previous session:', error);
      }
      setSessionId(null);
    }

    try {
      const recipe = await generateRecipe(allDetectedIngredients);
      setCurrentRecipe(recipe);
      setChatMessages([{
        type: 'bot',
        content: 'Tôi đã tạo công thức món ăn từ nguyên liệu của bạn! Bạn có muốn hỏi thêm chi tiết gì không?',
        timestamp: new Date()
      }]);
    } catch (error) {
      console.error('Error generating recipe:', error);
      setChatMessages([{
        type: 'bot',
        content: 'Xin lỗi, có lỗi khi tạo công thức. Vui lòng thử lại sau.',
        timestamp: new Date()
      }]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle manual chat input
  const handleSendChat = async () => {
    if (!chatInput.trim() || !sessionId || isStreaming) return;

    const question = chatInput;
    setChatInput('');
    
    await streamChatResponse(question);
  };

  // Handle quick question click
  const handleQuickQuestion = async (questionObj) => {
    if (!questionObj || !questionObj.question || !sessionId || isStreaming) return;
    
    setShowChat(true);
    await streamChatResponse(questionObj.question);
  };

  // Toggle chat visibility
  const toggleChat = () => {
    setShowChat(prev => !prev);
  };

  // Ingredients editing functions
  const handleEditIngredients = () => {
    setTempIngredients([...allDetectedIngredients]);
    setEditingIngredients(true);
  };

  const handleSaveIngredients = () => {
    setAllDetectedIngredients(tempIngredients.filter(ing => ing.trim()));
    setEditingIngredients(false);
  };

  const handleCancelEdit = () => {
    setTempIngredients([]);
    setEditingIngredients(false);
  };

  const handleAddIngredient = () => {
    setTempIngredients([...tempIngredients, '']);
  };

  const handleRemoveIngredient = (index) => {
    setTempIngredients(tempIngredients.filter((_, i) => i !== index));
  };

  const handleIngredientChange = (index, value) => {
    const updated = [...tempIngredients];
    updated[index] = value;
    setTempIngredients(updated);
  };

  // Cleanup session on unmount
  useEffect(() => {
    return () => {
      if (sessionId) {
        fetch(`http://localhost:5000/end-chat/${sessionId}`, {
          method: 'DELETE'
        }).catch(console.error);
      }
    };
  }, [sessionId]);

  return (
    <div className="food-app">
      {/* Left Panel */}
      <div className="left-panel">
        <div className="header">
          <div className="header-content">
            <ChefHat size={24} />
            <div>
              <h1>Nhận Diện Nguyên Liệu</h1>
              <p>Upload ảnh để AI phát hiện nguyên liệu</p>
            </div>
          </div>
        </div>

        <div className="upload-area">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept="image/*"
            multiple
            className="hidden"
          />
          <div 
            onClick={() => fileInputRef.current?.click()}
            className="upload-box"
          >
            <Upload className="upload-icon" />
            <p className="upload-text">Click để chọn ảnh</p>
            <p className="upload-subtext">Có thể chọn nhiều ảnh cùng lúc</p>
          </div>
        </div>

        <div className="images-list">
          {uploadedImages.map((image) => (
            <div key={image.id} className="image-item">
              <div className="image-content">
                <img 
                  src={image.url} 
                  alt={image.name}
                  className="image-thumbnail"
                />
                <div className="image-details">
                  <p className="image-name">{image.name}</p>
                  {image.detecting ? (
                    <div className="detecting">
                      <Loader2 size={16} className="loading-spinner" />
                      <span className="detecting-text">Đang phát hiện...</span>
                    </div>
                  ) : image.ingredients.length === 0 ? (
                    <div className="ingredients-tags empty-ingredients">
                      <span className="empty-ingredient-text">Không nhận diện được món nào</span>
                    </div>
                  ) : (
                    <div className="ingredients-tags">
                      {image.ingredients.map((ingredient, idx) => (
                        <span key={idx} className="ingredient-tag">
                          {ingredient}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleRemoveImage(image.id)}
                className="remove-btn"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>

        <div className="bottom-section">
          <div className="ingredients-header">
            <h3 className="ingredients-title">Tất cả nguyên liệu:</h3>
            {allDetectedIngredients.length > 0 && !editingIngredients && (
              <button
                onClick={handleEditIngredients}
                className="edit-btn"
              >
                <Edit3 size={12} />
                Sửa
              </button>
            )}
          </div>
          
          {editingIngredients ? (
            <div style={{ marginBottom: '16px' }}>
              {tempIngredients.map((ingredient, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <input
                    type="text"
                    value={ingredient}
                    onChange={(e) => handleIngredientChange(idx, e.target.value)}
                    style={{ 
                      flex: 1, 
                      padding: '6px 8px', 
                      border: '1px solid #d1d5db', 
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                    placeholder="Tên nguyên liệu"
                  />
                  <button
                    onClick={() => handleRemoveIngredient(idx)}
                    style={{
                      padding: '4px',
                      background: '#fee2e2',
                      color: '#dc2626',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                <button
                  onClick={handleAddIngredient}
                  style={{
                    padding: '6px 12px',
                    background: '#dbeafe',
                    color: '#1e40af',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  + Thêm
                </button>
                <button
                  onClick={handleSaveIngredients}
                  style={{
                    padding: '6px 12px',
                    background: '#dcfce7',
                    color: '#166534',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Check size={12} />
                  Lưu
                </button>
                <button
                  onClick={handleCancelEdit}
                  style={{
                    padding: '6px 12px',
                    background: '#f3f4f6',
                    color: '#6b7280',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  Hủy
                </button>
              </div>
            </div>
          ) : allDetectedIngredients.length > 0 ? (
            <div className="all-ingredients">
              {allDetectedIngredients.map((ingredient, idx) => (
                <span key={idx} className="all-ingredient-tag">
                  {ingredient}
                </span>
              ))}
            </div>
          ) : (
            <div className="all-ingredients empty-ingredients">
              <span className="empty-ingredient-text">Chưa có nguyên liệu nào</span>
            </div>
          )}
          
          <button
            onClick={handleGenerateRecipe}
            disabled={isProcessing || allDetectedIngredients.length === 0 || editingIngredients}
            className="generate-btn"
          >
            {isProcessing ? (
              <Loader2 size={16} className="loading-spinner" />
            ) : (
              <ChefHat size={16} />
            )}
            Tạo Công Thức Món Ăn
          </button>
        </div>
      </div>

      {/* Right Panel */}
      <div className="right-panel">
        <div className="recipe-header">
          <h2>Công Thức Món Ăn</h2>
          {allDetectedIngredients.length > 0 ? (
            <p>Được tạo từ {allDetectedIngredients.length} nguyên liệu</p>
          ) : (
            <p>Chưa phát hiện nguyên liệu nào</p>
          )}
        </div>
        
        {currentRecipe ? (
          <>
            <div className="recipe-content">
              <div className="recipe-text">{currentRecipe}</div>
            </div>
            
            {/* Fixed Common Questions Section */}
            <div className="quick-questions">
              <h4 className="quick-questions-title">
                <HelpCircle size={16} />
                Câu hỏi thường gặp
              </h4>
              <div className="quick-questions-grid">
                {commonQuestions.map((item, index) => {
                  const IconComponent = item.icon;
                  return (
                    <button
                      key={index}
                      className="quick-question-btn"
                      onClick={() => handleQuickQuestion(item)}
                      disabled={isStreaming || !sessionId}
                    >
                      <IconComponent size={14} className="question-icon" />
                      {item.text}
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-content">
              <ChefHat className="empty-icon" />
              <p className="empty-title">Chưa có công thức</p>
              <p className="empty-text">Upload ảnh và tạo công thức để bắt đầu</p>
            </div>
          </div>
        )}

        {currentRecipe && (
          <>
            <button
              className="toggle-chat-btn"
              onClick={toggleChat}
            >
              {showChat ? (
                <>
                  <ChevronUp className={`toggle-icon ${showChat ? 'rotated' : ''}`} size={20} />
                  Ẩn Chat
                </>
              ) : (
                <>
                  <ChevronDown className={`toggle-icon ${showChat ? '' : 'rotated'}`} size={20} />
                  Hiện Chat
                </>
              )}
            </button>
            
            <div className={`chat-section ${showChat ? 'visible' : 'hidden'}`}>
              <div className="chat-messages">
                {chatMessages.map((message, index) => (
                  <div key={index} className={`message ${message.type} ${message.isError ? 'error' : ''}`}>
                    <div className="message-content">
                      {message.content}
                    </div>
                  </div>
                ))}
                {isStreaming && (
                  <div className="streaming-indicator">
                    <Loader2 size={14} className="loading-spinner" style={{marginRight: '8px'}} />
                    Đang trả lời...
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
              
              <div className="chat-input">
                <div className="input-row">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendChat()}
                    placeholder={isStreaming ? "Đang trả lời..." : "Hỏi chi tiết về cách làm..."}
                    className="text-input"
                    disabled={isStreaming || !sessionId}
                  />
                  <button
                    onClick={handleSendChat}
                    disabled={isStreaming || !chatInput.trim() || !sessionId}
                    className="send-btn"
                  >
                    <Send size={16} />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default FoodDetectionApp;