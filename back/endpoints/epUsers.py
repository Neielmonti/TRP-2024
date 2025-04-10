from flask import Blueprint, request, jsonify,current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from extensions import mongo
from utils import generate_random_password
from flask_mail import Mail, Message

users_bp = Blueprint('users', __name__)


@users_bp.route('/users', methods=['GET'])
#@jwt_required()  # Puedes descomentar si requieres autenticación en este endpoint
def get_all_users():
    """
    Lista todos los usuarios con su experiencia acumulada y retorna los top 10.
    Se excluye la contraseña de la salida.
    """
    users_cursor = mongo.db.users.find()
    users_list = []
    
    for user in users_cursor:
        # Guardamos el _id original para la consulta
        original_id = user.get("_id")
        
        # Calcular la experiencia total acumulada para este usuario
        totalExp = 0
        answers = mongo.db.answers.find({"user_id": original_id})
        for answer in answers:
            # Obtener la pregunta correspondiente a la respuesta
            question = mongo.db.questions.find_one({"_id": answer["question_id"]})
            if question:
                try:
                    # Se asume que selectedOption es una cadena numérica y que las opciones comienzan en 1
                    idx = int(answer["selectedOption"]) - 1
                    if idx < len(question["options"]) and question["options"][idx].get("isCorrect") is True:
                        totalExp += question.get("exp", 0)
                except Exception as e:
                    print("Error procesando la respuesta:", e)
        
        # Agregar el campo de experiencia
        user["exp"] = totalExp
        
        # Excluir la contraseña
        user.pop("password", None)
        
        # Convertir el _id a cadena para serializar
        if "_id" in user:
            user["_id"] = str(user["_id"])
        
        users_list.append(user)

    # Ordenar la lista en orden descendente según la experiencia acumulada
    users_list_sorted = sorted(users_list, key=lambda x: x.get("exp", 0), reverse=True)
    
    # Retornar solo el top 10
    # top_10 = users_list_sorted[:10]
    return jsonify(users_list_sorted), 200

@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get("DNI")
    name = data.get("name")
    lastname = data.get("lastname")
    email = data.get("email")
    password = generate_random_password(12)
    print(password)
    if not username or not password:
        return jsonify({"error": "Faltan datos"}), 400

    if mongo.db.users.find_one({"username": username}):
        return jsonify({"error": "El usuario ya existe"}), 409

    hashed_password = generate_password_hash(password)
    mongo.db.users.insert_one({
        "DNI": username,
        "name": name,
        "lastname": lastname,
        "email": email,
        "password": hashed_password,
        "role": "user" 
    })

    msg = Message("Credenciales para el taller de resolución de problemas", recipients=[email])
    text_body = f"Hola {name},\n\nTu DNI para iniciar sesión es: {username}\n\nTu contraseña para iniciar sesión es: {password}\n\n¡Saludos!"
    html_body = f"""
    <p>Hola {name},</p>
    <p>Tu DNI para iniciar sesión es: <strong>{username}</strong></p>
    <p>Tu contraseña para iniciar sesión es: <strong>{password}</strong></p>
    <p>¡Saludos!</p>
    <p><u>Atte</u>: <u>Taller</u> <u>de</u> <u>resolución</u> <u>de</u> <u>problemas</u> <u>UNLu</u></p>
    """
    msg.body = text_body
    msg.html = html_body
    current_app.extensions['mail'].send(msg)

    return jsonify({"message": "Usuario registrado exitosamente. Se ha enviado un correo con la contraseña."}), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("DNI")
    password = data.get("password")
    
    user = mongo.db.users.find_one({"DNI": username})
    
    if user and check_password_hash(user["password"], password):
        access_token = create_access_token(identity=username)
        return jsonify({"access_token": access_token}), 200
    else:
        return jsonify({"error": "Credenciales inválidas"}), 401

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_username = get_jwt_identity()
    user = mongo.db.users.find_one({"DNI": current_username})
    if user:
        totalExp = 0
        # Se buscan todas las respuestas del usuario
        answers = mongo.db.answers.find({"user_id": user["_id"]})
        for answer in answers:
            # Se obtiene la pregunta correspondiente usando el question_id de la respuesta
            question = mongo.db.questions.find_one({"_id": answer["question_id"]})
            if question:
                try:
                    # Convertir selectedOption a índice (asumiendo que comienza en 1)
                    idx = int(answer["selectedOption"]) - 1
                    # Verificar que el índice exista en la lista de opciones y que la opción sea correcta
                    if idx < len(question["options"]) and question["options"][idx].get("isCorrect") is True:
                        totalExp += question.get("exp", 0)
                except Exception as e:
                    print("Error procesando la respuesta:", e)
        user_data = {
            "DNI": user.get("DNI"),
            "name": user.get("name"),
            "lastname": user.get("lastname"),
            "email": user.get("email"),
            "role": user.get("role"),
            "exp": totalExp  # Experiencia acumulada
        }
        return jsonify(user_data), 200
    return jsonify({"error": "Usuario no encontrado"}), 404
@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    # Obtener la identidad (DNI) del usuario logueado desde el token JWT
    current_dni = get_jwt_identity()
    
    # Recoger los datos enviados en el request
    data = request.get_json()
    
    if "currentPassword" not in data or "password" not in data:
        return jsonify({"error": "Debe proporcionar la contraseña actual y la nueva contraseña"}), 400

    current_password = data["currentPassword"]
    new_password = data["password"]

    user = mongo.db.users.find_one({"DNI": current_dni})
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Verificar si la contraseña actual es correcta.
    # Por ejemplo, suponiendo que usás check_password_hash
    if not check_password_hash(user.get("password", ""), current_password):
        return jsonify({"error": "Contraseña actual incorrecta"}), 401

    # Si la contraseña es correcta, actualizamos la contraseña (hasheada)
    mongo.db.users.update_one(
        {"DNI": current_dni},
        {"$set": {"password": generate_password_hash(new_password)}}
    )

    # Si la contraseña fue actualizada, enviar un correo de notificación
    if "password" in data:
        user = mongo.db.users.find_one({"DNI": current_dni})
        if user:
            email = user.get("email")
            name = user.get("name")
            lastname = user.get("lastname")
            username = user.get("DNI")  # Suponiendo que el DNI es el username
            # Configurar y enviar el correo
            msg = Message(
                "Cambio de contraseña",
                recipients=[email]
            )
            text_body = f"Hola {name} {lastname}, \n\nSe ha actualizado tu contraseña. \n\n¡Saludos!"
            html_body = f"""
            <p>Hola {name} {lastname}, </p>
            <p>Se ha actualizado tu contraseña.</p>
            <p>¡Saludos!</p>
            <p><u>Atte</u>: <u>Taller</u> <u>de</u> <u>resolución</u> <u>de</u> <u>problemas</u> <u>UNLu</u></p>
            """
            msg.body = text_body
            msg.html = html_body
            current_app.extensions['mail'].send(msg)

    return jsonify({"message": "Usuario actualizado exitosamente"}), 200
