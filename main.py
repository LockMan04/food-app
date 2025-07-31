from flask import Flask, request, jsonify
from flask_cors import CORS
from ultralytics import YOLO
import tempfile
import os
import json
import traceback
from openai import OpenAI

# Tạo Flask app
app = Flask(__name__)
CORS(app)

# Config
YOLO_MODEL_PATH = './models/best.pt'  # Đường dẫn đến model YOLO đã train
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"  # Chỉ là chuỗi giả
)

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
                final_ingredients = [item['name'] for item in sorted_results]
                
                print(f"🎯 Final ingredients: {final_ingredients}")
                
                return jsonify({
                    'success': True,
                    'ingredients': final_ingredients,
                    'detailed_results': sorted_results,
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
    
    return jsonify({
        'success': True,
        'classes': list(yolo_model.names.values()),
        'total_classes': len(yolo_model.names)
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
        prompt = f"""Từ các nguyên liệu: {ingredients_text}

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
Khi người dùng hỏi về món ăn này, hãy trả lời bằng tiếng Việt và cung cấp công thức chi tiết.
Nếu hỏi các câu hỏi ngoài lĩnh vực này, hãy trả lời rằng bạn chỉ chuyên về món ăn Việt Nam và không thể cung cấp thông tin khác."""

        try:
            print("🤖 Calling LM Studio API...")
            response = client.chat.completions.create(
                model="google/gemma-3-1b",  # hoặc tên model bạn đã cấu hình cho LM Studio
                messages=[
                    {"role": "system", "content": "Bạn là đầu bếp chuyên nghiệp, chuyên món ăn Việt Nam. Trả lời bằng tiếng Việt."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
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

# ==================== SMART QUESTIONS API ====================

@app.route('/generate-questions', methods=['POST'])
def api_generate_questions():
    """API endpoint để sinh câu hỏi thông minh"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'success': False
            }), 400
        
        ingredients = data.get('ingredients', [])
        recipe = data.get('recipe', None)
        
        if not ingredients:
            return jsonify({
                'error': 'No ingredients provided',
                'success': False
            }), 400
        
        ingredients_text = ', '.join(ingredients)
        
        prompt = f"""Dựa trên nguyên liệu: {ingredients_text}
{"Và công thức: " + recipe[:200] + "..." if recipe else ""}

Hãy tạo 4 câu hỏi phổ biến mà người dùng Việt Nam thường hỏi về món ăn này.

Trả về format JSON hợp lệ như sau:
[
  {{"text": "Câu hỏi ngắn hiển thị", "question": "Câu hỏi đầy đủ gửi cho bot", "category": "time"}},
  {{"text": "Câu hỏi ngắn hiển thị", "question": "Câu hỏi đầy đủ gửi cho bot", "category": "technique"}},
  {{"text": "Câu hỏi ngắn hiển thị", "question": "Câu hỏi đầy đủ gửi cho bot", "category": "portion"}},
  {{"text": "Câu hỏi ngắn hiển thị", "question": "Câu hỏi đầy đủ gửi cho bot", "category": "tips"}}
]

Categories chỉ được phép: time, technique, portion, tips"""

        try:
            print("🤖 Generating smart questions...")
            response = client.chat.completions.create(
                model="google/gemma-3-1b",
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia ẩm thực. Chỉ trả lời bằng JSON hợp lệ, không thêm text nào khác."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            content = response.choices[0].message.content.strip()
            print(f"📝 Raw response: {content}")
            
            # Parse JSON response
            questions = json.loads(content)
            
            # Validate structure
            if not isinstance(questions, list) or len(questions) != 4:
                raise ValueError("Invalid questions format")
            
            for q in questions:
                if not all(key in q for key in ['text', 'question', 'category']):
                    raise ValueError("Missing required fields in question")
            
            print("✅ Questions generated successfully")
            
            return jsonify({
                'success': True,
                'questions': questions,
                'total': len(questions)
            })
            
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON decode error: {str(json_error)}")
            return jsonify({
                'error': f'LM Studio trả về dữ liệu không hợp lệ: {str(json_error)}',
                'success': False,
                'troubleshooting': [
                    'Model có thể không hiểu yêu cầu JSON',
                    'Thử giảm max_tokens hoặc thay đổi prompt',
                    'Kiểm tra model có hỗ trợ JSON output không'
                ]
            }), 422
            
        except Exception as api_error:
            print(f"❌ LM Studio API error: {str(api_error)}")
            return jsonify({
                'error': f'Không thể kết nối tới LM Studio API: {str(api_error)}',
                'success': False,
                'troubleshooting': [
                    'Kiểm tra LM Studio có đang chạy không (localhost:1234)',
                    'Kiểm tra model đã được load chưa',
                    'Kiểm tra kết nối mạng'
                ]
            }), 503
        
    except Exception as e:
        print(f"❌ Generate questions error: {str(e)}")
        return jsonify({
            'error': f'Server error: {str(e)}',
            'success': False
        }), 500

# ==================== HEALTH & INFO ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
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
    
    return jsonify({
        'status': 'healthy',
        'yolo_model_loaded': model_loaded,
        'lm_studio_status': lm_studio_status,
        'lm_studio_url': 'http://localhost:1234/v1',
        'endpoints': [
            'POST /detect - YOLO detection',
            'GET /classes - Get YOLO classes',
            'POST /generate-recipe - Generate recipe',
            'POST /generate-questions - Generate smart questions',
            'GET /health - Health check'
        ]
    })

@app.route('/', methods=['GET'])
def root():
    """Root endpoint với thông tin API"""
    info = {
        'name': 'Food Detection & Recipe API',
        'version': '1.0.0',
        'status': 'running',
        'yolo_model': 'loaded' if model_loaded else 'failed',
        'endpoints': {
            'detection': {
                'POST /detect': 'Upload ảnh để detect nguyên liệu',
                'GET /classes': 'Lấy danh sách classes YOLO có thể detect'
            },
            'recipe': {
                'POST /generate-recipe': 'Tạo công thức từ nguyên liệu'
            },
            'questions': {
                'POST /generate-questions': 'Tạo câu hỏi thông minh'
            },
            'info': {
                'GET /health': 'Health check',
                'GET /': 'API information'
            }
        },
        'usage': {
            'detection': 'curl -X POST -F "image=@photo.jpg" http://localhost:5000/detect',
            'recipe': 'curl -X POST -H "Content-Type: application/json" -d \'{"ingredients":["thịt bò","cà rốt"]}\' http://localhost:5000/generate-recipe'
        }
    }
    
    return jsonify(info)

if __name__ == '__main__':
    print("🚀 Food Detection & Recipe API Server Starting...")
    print("=" * 50)
    print(f"📁 YOLO Model: {'✅ Loaded' if model_loaded else '❌ Failed'}")
    if model_loaded:
        print(f"🏷️  Detected Classes: {list(yolo_model.names.values())}")
    print(f"🤖 LM Studio URL: http://localhost:1234/v1")
    print("🌐 Server URL: http://localhost:5000")
    print("=" * 50)
    print("📋 Available Endpoints:")
    print("  POST /detect              - YOLO ingredient detection")
    print("  GET  /classes             - Get available classes")
    print("  POST /generate-recipe     - Generate recipe from ingredients")
    print("  POST /generate-questions  - Generate smart questions")
    print("  GET  /health              - Health check")
    print("  GET  /                    - API info")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)