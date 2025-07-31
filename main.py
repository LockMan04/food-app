from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from ultralytics import YOLO
import tempfile
import os
import json
import traceback
from openai import OpenAI
import uuid
from datetime import datetime, timedelta
import threading
import time
from flask import stream_with_context

# Tạo Flask app
app = Flask(__name__)
CORS(app)

# Config
YOLO_MODEL_PATH = './models/best.pt'  # Đường dẫn đến model YOLO đã train
model = "google/gemma-3-1b"  # Model LM Studio sử dụng
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"  # Chỉ là chuỗi giả
)

# Session storage (trong production nên dùng Redis)
chat_sessions = {}
session_lock = threading.Lock()

# Session cleanup thread
def cleanup_old_sessions():
    while True:
        with session_lock:
            current_time = datetime.now()
            expired_sessions = [
                session_id for session_id, session_data in chat_sessions.items()
                if current_time - session_data['last_activity'] > timedelta(hours=2)
            ]
            for session_id in expired_sessions:
                del chat_sessions[session_id]
        time.sleep(300)  # Check every 5 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_sessions, daemon=True)
cleanup_thread.start()

# Ingredient translation mapping
def datamap(ingredient):
    """
    Map English ingredient names to Vietnamese
    """
    translations = {
        "carrot": "Cà rốt",
        "chicken": "Thịt gà",
        "tomato": "Cà chua",
        "ginger": "Gừng",
        "beans": "Đậu",
        "banana": "Chuối",
        "sponge_gourd": "Mướp hương",
        "onion": "Hành tây",
        "garlic": "Tỏi",
        "bell_pepper": "Ớt chuông",
        "egg": "Trứng",
        "avocado": "Bơ",
        "beet": "Củ dền",
        "apple": "Táo",
        "lemon": "Chanh vàng",
        "broccoli": "Bông cải xanh",
        "bitter_gourd": "Khổ qua",
        "chillies": "Ớt",
        "fish": "Cá",
        "corn": "Bắp",
        "okra": "Đậu bắp",
        "eggplant": "Cà tím",
        "beef": "Thịt bò",
        "cucumber": "Dưa leo",
        "potato": "Khoai tây",
        "cabbage": "Bắp cải",
        "cauliflower": "Súp lơ trắng",
        "cheese": "Phô mai",
        "shrimp": "Tôm",
        "kimchi": "Kim chi",
        "lettuce": "Xà lách",
        "mushroom": "Nấm",
        "sausage": "Xúc xích",
        "coriander": "Rau mùi",
        "pineapple": "Thơm",
        "lime": "Chanh xanh",
        "papaya": "Đu đủ",
        "pork": "Thịt heo",
        "dragon_fruit": "Thanh long",
        "pumpkin": "Bí đỏ",
        "pear": "Lê",
        "guava": "Ổi",
        "calabash": "Bầu",
        "watermelon": "Dưa hấu",
        "turmeric": "Nghệ"
    }
    
    return translations.get(ingredient, ingredient)  # Trả về tên gốc nếu không tìm thấy

# Load YOLO model
print("🔄 Loading YOLO model...")
try:
    yolo_model = YOLO(YOLO_MODEL_PATH)
    print(f"✅ YOLO model loaded! Classes: {list(yolo_model.names.values())}")
    model_loaded = True
except Exception as e:
    print(f"❌ Failed to load YOLO model: {str(e)}")
    yolo_model = None
    model_loaded = False

# ==================== SESSION MANAGEMENT ====================

@app.route('/start-chat', methods=['POST'])
def start_chat():
    """Tạo session chat mới"""
    try:
        data = request.get_json() or {}
        ingredients = data.get('ingredients', [])
        recipe = data.get('recipe', '')
        
        session_id = str(uuid.uuid4())
        
        with session_lock:
            chat_sessions[session_id] = {
                'session_id': session_id,
                'ingredients': ingredients,
                'recipe': recipe,
                'messages': [],
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }
        
        print(f"✅ Created chat session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Chat session started successfully'
        })
        
    except Exception as e:
        print(f"❌ Start chat error: {str(e)}")
        return jsonify({
            'error': f'Failed to start chat: {str(e)}',
            'success': False
        }), 500

# ==================== YOLO DETECTION API ====================

@app.route('/detect', methods=['POST'])
def detect_ingredients():
    """
    API endpoint để detect nguyên liệu từ ảnh
    """
    try:
        if not model_loaded:
            return jsonify({
                'error': 'YOLO model not loaded',
                'success': False,
                'ingredients': []
            }), 500
        
        # Kiểm tra có file trong request không
        if 'image' not in request.files:
            return jsonify({
                'error': 'No image file provided',
                'success': False,
                'ingredients': []
            }), 400
        
        file = request.files['image']
        
        # Kiểm tra file có được chọn không
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'success': False,
                'ingredients': []
            }), 400
        
        if file and allowed_file(file.filename):
            temp_file_path = None
            try:
                # Lưu tạm thời với proper error handling
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    file.save(temp_file.name)
                    temp_file_path = temp_file.name
                
                print(f"🖼️ Processing image: {temp_file_path}")
                
                # Chạy YOLO detection với error handling
                results = yolo_model(temp_file_path, conf=0.3)
                print(f"🔍 YOLO results: {len(results)} result(s)")
                
                # Lấy tên nguyên liệu
                detailed_results = []
                
                for result in results:
                    print(f"📊 Processing result with {len(result.boxes) if result.boxes is not None else 0} boxes")
                    
                    if result.boxes is not None and len(result.boxes) > 0:
                        for i, box in enumerate(result.boxes):
                            try:
                                # Safely extract values
                                class_id = int(box.cls[0].item()) 
                                confidence = float(box.conf[0].item())
                                
                                # Check if class_id exists in model names
                                if class_id in yolo_model.names:
                                    class_name = yolo_model.names[class_id]
                                    
                                    detailed_results.append({
                                        'name': class_name,
                                        'confidence': confidence,
                                        'class_id': class_id
                                    })
                                    
                                    print(f"  ✅ Box {i}: {class_name} (confidence: {confidence:.3f})")
                                else:
                                    print(f"  ⚠️ Box {i}: Unknown class_id {class_id}")
                                    
                            except Exception as box_error:
                                print(f"  ❌ Error processing box {i}: {str(box_error)}")
                                continue
                
                print(f"📋 Total detections: {len(detailed_results)}")
                
                # Chỉ trả về tên, không trùng, sắp xếp theo confidence
                unique_ingredients = {}
                for item in detailed_results:
                    name = item['name']
                    if name not in unique_ingredients or item['confidence'] > unique_ingredients[name]['confidence']:
                        unique_ingredients[name] = item
                
                # Sort theo confidence giảm dần
                sorted_results = sorted(unique_ingredients.values(), key=lambda x: x['confidence'], reverse=True)
                
                # Translate ingredients to Vietnamese
                final_ingredients = []
                translated_results = []
                
                for item in sorted_results:
                    english_name = item['name']
                    vietnamese_name = datamap(english_name)
                    
                    final_ingredients.append(vietnamese_name)
                    translated_results.append({
                        'name': vietnamese_name,
                        'english_name': english_name,
                        'confidence': item['confidence'],
                        'class_id': item['class_id']
                    })
                
                print(f"🎯 Final ingredients (EN): {[item['name'] for item in sorted_results]}")
                print(f"🎯 Final ingredients (VI): {final_ingredients}")
                
                return jsonify({
                    'success': True,
                    'ingredients': final_ingredients,
                    'detailed_results': translated_results,
                    'total_detected': len(final_ingredients)
                })
                
            except Exception as detection_error:
                print(f"❌ Detection error: {str(detection_error)}")
                print(f"📍 Error traceback: {traceback.format_exc()}")
                
                return jsonify({
                    'error': f'Detection failed: {str(detection_error)}',
                    'success': False,
                    'ingredients': []
                }), 500
            
            finally:
                # Cleanup temp file
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                        print(f"🗑️ Cleaned up temp file: {temp_file_path}")
                    except Exception as cleanup_error:
                        print(f"⚠️ Failed to cleanup temp file: {str(cleanup_error)}")
        
        return jsonify({
            'error': 'Invalid file type. Supported: png, jpg, jpeg, gif, bmp, webp',
            'success': False,
            'ingredients': []
        }), 400
        
    except Exception as e:
        print(f"❌ Main error in detect_ingredients: {str(e)}")
        print(f"📍 Error traceback: {traceback.format_exc()}")
        return jsonify({
            'error': f'Server error: {str(e)}',
            'success': False,
            'ingredients': []
        }), 500

def allowed_file(filename):
    """Kiểm tra file có hợp lệ không"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/classes', methods=['GET'])
def get_classes():
    """
    API để lấy danh sách các class mà model có thể detect
    """
    if not model_loaded:
        return jsonify({
            'error': 'YOLO model not loaded',
            'success': False
        }), 500
    
    # Get English classes and translate to Vietnamese
    english_classes = list(yolo_model.names.values())
    vietnamese_classes = [datamap(cls) for cls in english_classes]
    
    # Create mapping for reference
    class_mapping = {}
    for i, english_name in enumerate(english_classes):
        vietnamese_name = datamap(english_name)
        class_mapping[i] = {
            'english': english_name,
            'vietnamese': vietnamese_name
        }
    
    return jsonify({
        'success': True,
        'classes': vietnamese_classes,
        'english_classes': english_classes,
        'class_mapping': class_mapping,
        'total_classes': len(english_classes)
    })

# ==================== LM STUDIO RECIPE API ====================

@app.route('/generate-recipe', methods=['POST'])
def generate_recipe():
    """
    API endpoint để tạo công thức từ nguyên liệu
    """
    try:
        data = request.get_json()
        
        if not data or 'ingredients' not in data:
            return jsonify({
                'error': 'No ingredients provided',
                'success': False
            }), 400
        
        ingredients = data['ingredients']
        
        if not ingredients:
            return jsonify({
                'error': 'Ingredients list is empty',
                'success': False
            }), 400
        
        # Tạo prompt cho LM Studio
        ingredients_text = ', '.join(ingredients)
        prompt = f"""
Bạn là một đầu bếp Việt Nam chuyên nghiệp. Bạn chỉ được phép trả lời về các món ăn Việt Nam, đặc biệt là đưa ra gợi ý món ăn dựa trên nguyên liệu có sẵn.
Từ các nguyên liệu: {ingredients_text}

Hãy gợi ý 3 món ăn Việt Nam phù hợp với công thức chi tiết bao gồm:

🍲 [Tên món ăn]

Nguyên liệu chính: {ingredients_text}

Nguyên liệu thêm:
- [Liệt kê nguyên liệu cần thêm]

Cách làm:
1. Sơ chế: [Hướng dẫn sơ chế]
2. Nấu: [Các bước nấu chi tiết]
3. Nêm nếm: [Cách nêm nếm]
4. Hoàn thành: [Bước cuối cùng]

⏱️ Thời gian: [X phút] | 🌟 Độ khó: [Dễ/Trung bình/Khó]

Lưu ý: Hướng dẫn phải rõ ràng, dễ hiểu, phù hợp với người Việt.
Trả về định dạng text thường, không thêm các tag HTML hay Markdown hoặc các ký tự đặc biệt khác.
Khi người dùng hỏi về món ăn này, hãy trả lời bằng tiếng Việt và cung cấp công thức chi tiết.
Nếu hỏi các câu hỏi ngoài lĩnh vực này, hãy trả lời rằng bạn chỉ chuyên về món ăn Việt Nam và không thể cung cấp thông tin khác.
"""
        try:
            print("🤖 Calling LM Studio API...")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Bạn là đầu bếp chuyên nghiệp, chuyên món ăn Việt Nam. Trả lời bằng tiếng Việt."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )
            
            recipe = response.choices[0].message.content
            print("✅ Recipe generated successfully")
            
            return jsonify({
                'success': True,
                'recipe': recipe,
                'ingredients_used': ingredients
            })
            
        except Exception as api_error:
            print(f"❌ LM Studio API error: {str(api_error)}")
            return jsonify({
                'error': f'Không thể kết nối tới LM Studio API. Vui lòng kiểm tra: {str(api_error)}',
                'success': False,
                'troubleshooting': [
                    'Kiểm tra LM Studio có đang chạy không (localhost:1234)',
                    'Kiểm tra model đã được load chưa',
                    'Kiểm tra kết nối mạng',
                    'Xem lại cấu hình API endpoint'
                ]
            }), 503
            
    except Exception as e:
        print(f"❌ Generate recipe error: {str(e)}")
        return jsonify({
            'error': f'Server error: {str(e)}',
            'success': False
        }), 500

# ==================== CHAT API WITH CONTEXT & STREAMING ====================

@app.route('/chat-stream', methods=['POST'])
def chat_stream():
    """Chat với streaming response và context memory"""
    data = request.get_json()
    session_id = data.get('session_id')
    question = data.get('question', '')

    @stream_with_context
    def generate_response():
        try:
            if not session_id or not question:
                yield f"data: {json.dumps({'error': 'Missing session_id or question', 'type': 'error'})}\n\n"
                return
            # Get session
            with session_lock:
                if session_id not in chat_sessions:
                    yield f"data: {json.dumps({'error': 'Session not found or expired', 'type': 'error'})}\n\n"
                    return
                session = chat_sessions[session_id]
                session['last_activity'] = datetime.now()
            # Build context from previous messages
            ingredients_text = ', '.join(session['ingredients']) if session['ingredients'] else "các nguyên liệu có sẵn"
            recipe_context = session['recipe'][:400] if session['recipe'] else ""
            system_prompt = f"""
                Bạn là một chuyên gia ẩm thực Việt Nam chuyên nghiệp. 
                Bạn chỉ có thể trả lời các câu hỏi liên quan đến nấu ăn, nguyên liệu, món ăn, công thức hoặc mẹo vặt nhà bếp.

                Nguyên liệu hiện có: {ingredients_text}
                Công thức đang thảo luận: {recipe_context}

                QUY TẮC BẮT BUỘC:
                - Bạn TUYỆT ĐỐI KHÔNG được trả lời bất kỳ nội dung nào ngoài nấu ăn, kể cả khi người dùng hỏi về lập trình, khoa học, game, hay bất kỳ lĩnh vực nào khác. Bạn chỉ được phép nói đúng câu: "Xin lỗi tôi chỉ có thể trả lời về nấu ăn. Nếu bạn có câu hỏi nào khác, hãy cho tôi biết."
                - KHÔNG được suy luận hoặc trả lời bất kỳ thông tin nào ngoài lĩnh vực ẩm thực.
                - Trả lời ngắn gọn, dễ hiểu, đúng trọng tâm, bằng tiếng Việt.
                - KHÔNG dùng HTML, Markdown, hoặc ký tự đặc biệt.
                - Trả lời theo dạng văn bản thường, không có định dạng phức tạp, xuống dòng hợp lý.
                - Duy trì giọng điệu lịch sự, chuyên nghiệp nhưng gần gũi.

                LƯU Ý: Luôn bám sát nguyên liệu và công thức đang thảo luận nếu có.
                """
            context_messages = [{"role": "system", "content": system_prompt}]
            # Add previous conversation history (last 8 messages)
            for msg in session['messages'][-8:]:
                context_messages.append({"role": "user", "content": msg['question']})
                context_messages.append({"role": "assistant", "content": msg['answer']})
            # Add current question
            context_messages.append({"role": "user", "content": question})
            print(f"🤖 Streaming chat - Session: {session_id}, Question: {question[:50]}...")
            # Stream response từ LM Studio
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=context_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=500
                )
                full_answer = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_answer += content
                        yield f"data: {json.dumps({'content': content, 'type': 'chunk'})}\n\n"
                # Save complete answer to session
                with session_lock:
                    if session_id in chat_sessions:
                        chat_sessions[session_id]['messages'].append({
                            'question': question,
                            'answer': full_answer.strip(),
                            'timestamp': datetime.now().isoformat()
                        })
                        chat_sessions[session_id]['last_activity'] = datetime.now()
                yield f"data: {json.dumps({'type': 'done', 'full_answer': full_answer.strip()})}\n\n"
                print("✅ Streaming response completed")
            except Exception as api_error:
                print(f"❌ LM Studio API error: {str(api_error)}")
                # Fallback response based on question keywords
                question_lower = question.lower()
                fallback_answer = ""
                if 'thời gian' in question_lower or 'bao lâu' in question_lower:
                    fallback_answer = 'Thời gian chuẩn bị khoảng 10 phút, nấu 15-20 phút. Tổng cộng khoảng 25-30 phút là xong nhé!'
                elif 'lửa' in question_lower or 'nhiệt độ' in question_lower:
                    fallback_answer = 'Nên dùng lửa vừa khi xào thịt, lửa to khi đun sôi nước. Lưu ý đảo đều tay để không bị cháy!'
                elif 'người' in question_lower or 'khẩu phần' in question_lower:
                    fallback_answer = 'Công thức này đủ cho 3-4 người ăn. Nếu muốn nhiều hơn thì nhân đôi nguyên liệu nhé!'
                elif 'mẹo' in question_lower or 'ngon' in question_lower:
                    fallback_answer = 'Mẹo: ướp thịt kỹ trước khi nấu, rau củ không nên xào quá lâu để giữ độ giòn. Nêm nếm từ từ cho vừa miệng!'
                elif 'dai' in question_lower and 'thịt' in question_lower:
                    fallback_answer = 'Để thịt không dai: ướp với chút muối và dầu ăn 15 phút trước khi nấu, không nấu quá lâu ở nhiệt độ cao!'
                elif 'xanh' in question_lower and ('rau' in question_lower or 'cải' in question_lower):
                    fallback_answer = 'Để rau giữ màu xanh: cho rau vào khi nước đã sôi, nấu nhanh ở lửa to, vớt ra ngay khi chín tới!'
                else:
                    fallback_answer = 'Dựa trên nguyên liệu và công thức hiện tại, tôi khuyên bạn nên chú ý đến độ chín của nguyên liệu và nêm nếm phù hợp. Nấu ăn cần kiên nhẫn và thử nếm để có món ăn ngon nhất!'
                # Stream fallback answer word by word
                words = fallback_answer.split(' ')
                full_fallback = ""
                for word in words:
                    full_fallback += word + " "
                    yield f"data: {json.dumps({'content': word + ' ', 'type': 'chunk'})}\n\n"
                    time.sleep(0.05)  # Small delay for streaming effect
                # Save fallback to session
                with session_lock:
                    if session_id in chat_sessions:
                        chat_sessions[session_id]['messages'].append({
                            'question': question,
                            'answer': fallback_answer,
                            'timestamp': datetime.now().isoformat()
                        })
                yield f"data: {json.dumps({'type': 'done', 'full_answer': fallback_answer, 'note': 'Fallback response'})}\n\n"
        except Exception as e:
            print(f"❌ Chat stream error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"

    return Response(
        generate_response(),
        mimetype='text/plain',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )

@app.route('/get-chat-history/<session_id>', methods=['GET'])
def get_chat_history(session_id):
    """Lấy lịch sử chat"""
    try:
        with session_lock:
            if session_id not in chat_sessions:
                return jsonify({
                    'error': 'Session not found',
                    'success': False
                }), 404
            
            session = chat_sessions[session_id]
            
        return jsonify({
            'success': True,
            'session_id': session_id,
            'ingredients': session['ingredients'],
            'recipe': session['recipe'],
            'messages': session['messages'],
            'created_at': session['created_at'].isoformat(),
            'last_activity': session['last_activity'].isoformat(),
            'total_messages': len(session['messages'])
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Server error: {str(e)}',
            'success': False
        }), 500

@app.route('/end-chat/<session_id>', methods=['DELETE'])
def end_chat(session_id):
    """Kết thúc session chat"""
    try:
        with session_lock:
            if session_id in chat_sessions:
                del chat_sessions[session_id]
                print(f"🗑️ Ended chat session: {session_id}")
                return jsonify({
                    'success': True,
                    'message': 'Chat session ended'
                })
            else:
                return jsonify({
                    'error': 'Session not found',
                    'success': False
                }), 404
                
    except Exception as e:
        return jsonify({
            'error': f'Server error: {str(e)}',
            'success': False
        }), 500

# ==================== HEALTH & INFO ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint with session info"""
    try:
        # Test LM Studio connection
        lm_studio_status = "unknown"
        try:
            test_response = client.chat.completions.create(
                model="google/gemma-3-1b",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=5
            )
            lm_studio_status = "connected"
        except Exception as e:
            lm_studio_status = f"disconnected: {str(e)}"
        
        # Session statistics
        with session_lock:
            active_sessions = len(chat_sessions)
            session_stats = {
                'active_sessions': active_sessions,
                'sessions': [
                    {
                        'session_id': sid,
                        'messages_count': len(data['messages']),
                        'last_activity': data['last_activity'].isoformat(),
                        'ingredients_count': len(data['ingredients'])
                    }
                    for sid, data in chat_sessions.items()
                ]
            }
        
        return jsonify({
            'status': 'healthy',
            'yolo_model_loaded': model_loaded,
            'lm_studio_status': lm_studio_status,
            'lm_studio_url': 'http://localhost:1234/v1',
            'session_stats': session_stats,
            'endpoints': [
                'POST /detect - YOLO detection',
                'GET /classes - Get YOLO classes',
                'POST /generate-recipe - Generate recipe',
                'POST /start-chat - Start chat session',
                'POST /chat-stream - Chat with streaming & context',
                'GET /get-chat-history/<id> - Get chat history',
                'DELETE /end-chat/<id> - End chat session',
                'GET /health - Health check'
            ]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint với thông tin API"""
    info = {
        'name': 'Food Detection & Recipe API with Context Chat',
        'version': '2.0.0',
        'status': 'running',
        'yolo_model': 'loaded' if model_loaded else 'failed',
        'features': [
            'YOLO ingredient detection',
            'LM Studio recipe generation',
            'Context-aware streaming chat',
            'Session management',
            'Chat history'
        ],
        'endpoints': {
            'detection': {
                'POST /detect': 'Upload ảnh để detect nguyên liệu',
                'GET /classes': 'Lấy danh sách classes YOLO có thể detect'
            },
            'recipe': {
                'POST /generate-recipe': 'Tạo công thức từ nguyên liệu'
            },
            'chat': {
                'POST /start-chat': 'Bắt đầu session chat với context',
                'POST /chat-stream': 'Chat với streaming response',
                'GET /get-chat-history/<id>': 'Lấy lịch sử chat',
                'DELETE /end-chat/<id>': 'Kết thúc session chat'
            },
            'info': {
                'GET /health': 'Health check',
                'GET /': 'API information'
            }
        },
        'usage': {
            'detection': 'curl -X POST -F "image=@photo.jpg" http://localhost:5000/detect',
            'recipe': 'curl -X POST -H "Content-Type: application/json" -d \'{"ingredients":["thịt bò","cà rốt"]}\' http://localhost:5000/generate-recipe',
            'chat': 'curl -X POST -H "Content-Type: application/json" -d \'{"ingredients":["thịt bò"],"recipe":"..."}\' http://localhost:5000/start-chat'
        }
    }
    
    return jsonify(info)

if __name__ == '__main__':
    print("🚀 Food Detection & Recipe API with Context Chat Starting...")
    print("=" * 60)
    print(f"📁 YOLO Model: {'✅ Loaded' if model_loaded else '❌ Failed'}")
    if model_loaded:
        print(f"🏷️  Detected Classes: {list(yolo_model.names.values())}")
    print(f"🤖 LM Studio URL: http://localhost:1234/v1")
    print("🌐 Server URL: http://localhost:5000")
    print("=" * 60)
    print("📋 Available Endpoints:")
    print("  POST /detect                    - YOLO ingredient detection")
    print("  GET  /classes                   - Get available classes")
    print("  POST /generate-recipe           - Generate recipe from ingredients")
    print("  POST /start-chat                - Start chat session with context")
    print("  POST /chat-stream               - Chat with streaming response")
    print("  GET  /get-chat-history/<id>     - Get chat history")
    print("  DELETE /end-chat/<id>           - End chat session")
    print("  GET  /health                    - Health check")
    print("  GET  /                          - API info")
    print("=" * 60)
    print("🆕 New Features:")
    print("  ✅ Session-based context memory")
    print("  ✅ Real-time streaming responses")
    print("  ✅ Chat history storage")
    print("  ✅ Automatic session cleanup")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)