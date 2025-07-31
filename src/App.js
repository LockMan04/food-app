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
  const [quickQuestions] = useState([
    { icon: Clock, text: "Thời gian nấu bao lâu?", question: "Thời gian nấu món này mất bao lâu?" },
    { icon: Flame, text: "Nhiệt độ bao nhiêu?", question: "Nên dùng lửa to hay lửa nhỏ?" },
    { icon: Users, text: "Đủ cho mấy người?", question: "Công thức này đủ cho bao nhiêu người ăn?" },
    { icon: HelpCircle, text: "Mẹo nấu ngon?", question: "Có mẹo gì để món ăn ngon hơn không?" }
  ]);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // Scroll to bottom when chatMessages change
  useEffect(() => {
    if (chatEndRef.current && showChat) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, showChat]);

  // YOLO detection
  const detectIngredients = async (imageFile) => {
    const formData = new FormData();
    formData.append('image', imageFile);
    
    const response = await fetch('http://localhost:5000/detect', {
      method: 'POST', body: formData
    });
    
    const data = await response.json();
    return data.ingredients;
  };


  // Recipe generation
  const generateRecipe = async (ingredients) => {
  const response = await fetch('http://localhost:5000/generate-recipe', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ingredients})
  });
  
  const data = await response.json();
  return data.recipe;
};

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
        
        setTimeout(async () => {
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
    try {
      const recipe = await generateRecipe(allDetectedIngredients);
      setCurrentRecipe(recipe);
      setChatMessages([{
        type: 'bot',
        content: 'Tôi đã tạo công thức món ăn từ nguyên liệu của bạn! Bạn có muốn hỏi thêm chi tiết gì không?',
        timestamp: new Date()
      }]);
      // Không tự động show chat nữa
    } catch (error) {
      console.error('Error generating recipe:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || !currentRecipe) return;

    const userMessage = {
      type: 'user',
      content: chatInput,
      timestamp: new Date()
    };

    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setIsProcessing(true);

    setTimeout(() => {
      let response = '';
      const question = chatInput.toLowerCase();
      
      if (question.includes('thời gian') || question.includes('bao lâu')) {
        response = 'Thời gian chuẩn bị khoảng 10 phút, nấu 15 phút. Tổng cộng khoảng 25 phút là xong nhé!';
      } else if (question.includes('lửa') || question.includes('nhiệt độ')) {
        response = 'Nên dùng lửa vừa khi xào thịt, lửa to khi đun sôi nước. Lưu ý đảo đều tay để không bị cháy!';
      } else if (question.includes('người') || question.includes('khẩu phần')) {
        response = 'Công thức này đủ cho 3-4 người ăn. Nếu muốn nhiều hơn thì nhân đôi nguyên liệu nhé!';
      } else if (question.includes('mẹo') || question.includes('ngon')) {
        response = 'Mẹo: ướp thịt kỹ trước khi nấu, rau củ không nên xào quá lâu để giữ độ giòn. Nêm nếm từ từ cho vừa miệng!';
      } else {
        response = 'Câu hỏi hay đó! Dựa trên công thức hiện tại, tôi khuyên bạn nên chú ý đến độ chín của nguyên liệu.';
      }

      setChatMessages(prev => [...prev, {
        type: 'bot',
        content: response,
        timestamp: new Date()
      }]);
      setIsProcessing(false);
    }, 1000);
  };

  const handleQuickQuestion = (questionText) => {
    setShowChat(true); // Hiện chat khi chọn câu hỏi phổ biến
    setChatInput(questionText);
    // Auto send the question
    setTimeout(() => {
      const userMessage = {
        type: 'user',
        content: questionText,
        timestamp: new Date()
      };

      setChatMessages(prev => [...prev, userMessage]);
      setChatInput('');
      setIsProcessing(true);

      // Generate response based on question
      setTimeout(() => {
        let response = '';
        const question = questionText.toLowerCase();
        
        if (question.includes('thời gian') || question.includes('bao lâu')) {
          response = 'Thời gian chuẩn bị khoảng 10 phút, nấu 15 phút. Tổng cộng khoảng 25 phút là xong nhé!';
        } else if (question.includes('lửa') || question.includes('nhiệt độ')) {
          response = 'Nên dùng lửa vừa khi xào thịt, lửa to khi đun sôi nước. Lưu ý đảo đều tay để không bị cháy!';
        } else if (question.includes('người') || question.includes('khẩu phần')) {
          response = 'Công thức này đủ cho 3-4 người ăn. Nếu muốn nhiều hơn thì nhân đôi nguyên liệu nhé!';
        } else if (question.includes('mẹo') || question.includes('ngon')) {
          response = 'Mẹo: ướp thịt kỹ trước khi nấu, rau củ không nên xào quá lâu để giữ độ giòn. Nêm nếm từ từ cho vừa miệng!';
        } else {
          response = 'Câu hỏi hay đó! Dựa trên công thức hiện tại, tôi khuyên bạn nên chú ý đến độ chín của nguyên liệu.';
        }

        setChatMessages(prev => [...prev, {
          type: 'bot',
          content: response,
          timestamp: new Date()
        }]);
        setIsProcessing(false);
      }, 1000);
    }, 100);
  };

  const toggleChat = () => {
    setShowChat(prev => !prev);
  };

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
            
            {/* Quick Questions Section */}
            <div className="quick-questions">
              <h4 className="quick-questions-title">
                <HelpCircle size={16} />
                Câu hỏi phổ biến
              </h4>
              <div className="quick-questions-grid">
                {quickQuestions.map((item, index) => (
                  <button
                    key={index}
                    className="quick-question-btn"
                    onClick={() => handleQuickQuestion(item.question)}
                  >
                    <item.icon size={14} className="question-icon" />
                    {item.text}
                  </button>
                ))}
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
                  <div key={index} className={`message ${message.type}`}>
                    <div className="message-content">
                      {message.content}
                    </div>
                  </div>
                ))}
                {isProcessing && (
                  <div className="message bot">
                    <div className="message-content">
                      <Loader2 size={14} className="loading-spinner" style={{marginRight: '8px'}} />
                      Đang trả lời...
                    </div>
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
                    placeholder="Hỏi chi tiết về cách làm..."
                    className="text-input"
                    disabled={isProcessing}
                  />
                  <button
                    onClick={handleSendChat}
                    disabled={isProcessing || !chatInput.trim()}
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