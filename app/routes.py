from flask import Blueprint, request, jsonify
from . import db
from .models import User, Product, Sales
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import datetime

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
        return jsonify({'message': 'User already exists'}), 400

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id, additional_claims={
            'username': user.username,
            'role': user.role
        })
        return jsonify({'access_token': access_token}), 200

    return jsonify({'message': 'Invalid credentials'}), 401

@bp.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return jsonify({'message': f'Welcome {user.username}!', 'user_id': user.id}), 200

# Stock Management Routes

@bp.route('/stock', methods=['POST'])
@jwt_required()
def add_stock():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    data = request.get_json()
    product_name = data.get('product_name')
    quantity = data.get('quantity')
    alarm_at = data.get('alarm_at')
    price = data.get('price')
    image_path = data.get('image_path', '')

    product = Product(product_name=product_name, quantity=quantity, alarm_at=alarm_at, price=price, image_path=image_path)
    db.session.add(product)
    db.session.commit()

    return jsonify({'message': 'Product added successfully', 'product_id': product.id}), 201

@bp.route('/stock/<int:product_id>', methods=['PUT'])
@jwt_required()
def edit_stock(product_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    data = request.get_json()
    product = Product.query.get_or_404(product_id)

    if 'product_name' in data:
        product.product_name = data['product_name']
    if 'quantity' in data:
        product.quantity = data['quantity']
    if 'alarm_at' in data:
        product.alarm_at = data['alarm_at']
    if 'price' in data:
        product.price = data['price']
    if 'image_path' in data:
        product.image_path = data['image_path']

    product.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Product updated successfully'}), 200

@bp.route('/stock/<int:product_id>', methods=['DELETE'])
@jwt_required()
def soft_delete_stock(product_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    product = Product.query.get_or_404(product_id)
    product.deleted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Product deleted successfully'}), 200

@bp.route('/stock', methods=['GET'])
@jwt_required()
def list_stock():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403

    products = Product.query.filter_by(deleted_at=None).all()
    product_list = [
        {
            'id': product.id,
            'product_name': product.product_name,
            'quantity': product.quantity,
            'alarm_at': product.alarm_at,
            'price': product.price,
            'created_at': product.created_at,
            'updated_at': product.updated_at,
            'status': product.status,
            'image_path': product.image_path
        } for product in products
    ]
    return jsonify(product_list), 200


# Product Listing API
@bp.route('/products', methods=['GET'])
@jwt_required()
def list_products():
    products = Product.query.filter_by(deleted_at=None).all()
    product_list = [
        {
            'id': product.id,
            'product_name': product.product_name,
            'quantity': product.quantity,
            'price': product.price,
            'alarm_at': product.alarm_at,
            'status': product.status,
            'image_path': product.image_path
        } for product in products
    ]
    return jsonify(product_list), 200

# Purchase API
@bp.route('/purchase/<int:product_id>', methods=['POST'])
@jwt_required()
def purchase_product(product_id):
    user_id = get_jwt_identity()
    product = Product.query.get_or_404(product_id)
    
    if product.quantity <= 0:
        return jsonify({'message': 'Product out of stock'}), 400
    
    product.quantity -= 1
    db.session.commit()

    # Check for alarm condition
    if product.quantity <= product.alarm_at:
        alarm_message = f'Alarm: Product {product.product_name} quantity is below or at alarm level.'
    else:
        alarm_message = None

    # Add to sales table
    sale = Sales(user_id=user_id, product_id=product_id, price=product.price, quantity=1, created_at=datetime.utcnow())
    db.session.add(sale)
    db.session.commit()

    return jsonify({'message': 'Product purchased successfully', 'alarm_message': alarm_message}), 200