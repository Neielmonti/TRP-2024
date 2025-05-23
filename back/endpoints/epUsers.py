import io, csv
from flask import Blueprint, request, jsonify,current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from extensions import mongo
from utils import generate_random_password
from flask_mail import Mail, Message
from bson import ObjectId
from werkzeug.utils import secure_filename

mail=Mail()

users_bp = Blueprint('users', __name__)



@users_bp.route('/users', methods=['GET'])
##@jwt_required()
def get_users():
    users = mongo.db.users.find()
    all_users_data = []
    
    for user in users:
        totalExp = 0
        # Se buscan todas las respuestas del usuario
        answers = mongo.db.answers.find({"user_id": user["_id"]})
        
        # Cargar las preguntas en un diccionario para evitar múltiples consultas
        questions = {q["_id"]: q for q in mongo.db.questions.find()}
        
        for answer in answers:
            question = questions.get(answer["question_id"])
            if question:
                print(f"Procesando respuesta para la pregunta {question['_id']}")  # Depuración
                try:
                    # Procesar preguntas del tipo "choice"
                    if "selectedOption" in answer:
                        idx = int(answer["selectedOption"])
                        print(f"Índice de opción seleccionada: {idx}")  # Depuración
                        # Verificar que el índice sea válido y que la opción seleccionada sea correcta
                        if 0 <= idx < len(question["options"]):
                            selected_option = question["options"][idx]
                            print(f"Verificando opción: {selected_option}")  # Depuración
                            if selected_option.get("isCorrect"):
                                totalExp += question.get("exp", 0)
                                print(f"Experiencia sumada: {question.get('exp', 0)}")  # Depuración
                    
                    # Procesar preguntas del tipo "OpenEntry"
                    elif "body" in answer:
                        print(f"Verificando respuesta abierta: {answer['body']}")  # Depuración
                        # Aquí puedes agregar la lógica para evaluar la respuesta de tipo OpenEntry
                        # Ejemplo de validación:
                        if validate_open_entry_answer(question, answer["body"]):
                            totalExp += question.get("exp", 0)
                            print(f"Experiencia sumada por OpenEntry: {question.get('exp', 0)}")  # Depuración

                except (ValueError, IndexError) as e:
                    print(f"Error procesando la respuesta: {e}")  # Depuración
        
        user_data = {
            "user_id": user.get("_id"),
            "DNI": user.get("DNI"),
            "name": user.get("name"),
            "lastname": user.get("lastname"),
            "email": user.get("email"),
            "role": user.get("role"),
            "exp": totalExp  # Experiencia acumulada
        }
        
        all_users_data.append(user_data)
    
    return jsonify(all_users_data), 200


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

@users_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    current_dni = get_jwt_identity()

    # Buscar usuario por su DNI
    user = mongo.db.users.find_one({"DNI": current_dni})

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    totalExp = 0

    # Obtener todas las respuestas del usuario
    answers = mongo.db.answers.find({"user_id": user["_id"]})

    # Cargar todas las preguntas
    questions = {q["_id"]: q for q in mongo.db.questions.find()}

    for answer in answers:
        question = questions.get(answer["question_id"])
        if question:
            try:
                # Procesar multiple choice
                if "selectedOption" in answer:
                    idx = int(answer["selectedOption"])
                    if 0 <= idx < len(question.get("options", [])):
                        selected_option = question["options"][idx]
                        if selected_option.get("isCorrect"):
                            totalExp += question.get("exp", 0)

                # Procesar OpenEntry
                elif "body" in answer:
                    if validate_open_entry_answer(question, answer["body"]):
                        totalExp += question.get("exp", 0)

            except (ValueError, IndexError) as e:
                print(f"Error procesando respuesta: {e}")

    profile = {
        "userId": str(user["_id"]),
        "DNI": user["DNI"],
        "name": user["name"],
        "lastname": user["lastname"],
        "email": user["email"],
        "role": user.get("role", ""),
        "exp": totalExp,
    }

    return jsonify(profile)



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
def validate_open_entry_answer(question, user_answer):
    # Validar la respuesta abierta
    correct_answer = question.get("expectedAnswer", "").strip().lower()
    user_answer = user_answer.strip().lower()
    print(f"Validando respuesta abierta: '{user_answer}' == '{correct_answer}'")  # Depuración
    return user_answer == correct_answer

@users_bp.route('/user-progress', methods=['GET'])
@jwt_required()
def get_user_progress():
    current_dni = get_jwt_identity()
    user = mongo.db.users.find_one({"DNI": current_dni})

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    user_id = user["_id"]

    # Obtener todas las respuestas del usuario
    answers = mongo.db.answers.find({"user_id": user_id})

    # Cargar todas las preguntas en un diccionario para acceso rápido
    questions = {q["_id"]: q for q in mongo.db.questions.find()}

    # Inicializar un diccionario para almacenar el progreso por unidad
    progress_by_unit = {}

    for answer in answers:
        question_id = answer.get("question_id")
        question = questions.get(question_id)

        if not question:
            continue

        unit_id = str(question.get("unit_id"))

        # Verificar si la respuesta es correcta
        is_correct = False
        if "selectedOption" in answer:
            try:
                idx = int(answer["selectedOption"])
                options = question.get("options", [])
                if 0 <= idx < len(options):
                    selected_option = options[idx]
                    is_correct = selected_option.get("isCorrect", False)
            except (ValueError, IndexError):
                continue
        elif "body" in answer:
            correct_answer = question.get("expectedAnswer", "").strip().lower()
            user_answer = answer["body"].strip().lower()
            is_correct = user_answer == correct_answer

        if is_correct:
            if unit_id not in progress_by_unit:
                progress_by_unit[unit_id] = []
            progress_by_unit[unit_id].append(str(question_id))

    return jsonify(progress_by_unit), 200

@users_bp.route('/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        result = mongo.db.users.delete_one({"_id": ObjectId(user_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Eliminar también las respuestas asociadas a ese usuario, si aplica
        mongo.db.answers.delete_many({"user_id": ObjectId(user_id)})

        return jsonify({"message": "Usuario eliminado exitosamente"}), 200

    except Exception as e:
        return jsonify({"error": f"Error eliminando usuario: {str(e)}"}), 500
@users_bp.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])  # Convertir ObjectId a string
            return jsonify(user), 200
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": f"Error obteniendo usuario: {str(e)}"}), 500
    
@users_bp.route('/users/<id>', methods=['PUT'])
#@jwt_required()
def update_user(id):
    """
    Actualiza campos de un usuario dado su _id de MongoDB,
    incluyendo opcionalmente el cambio de contraseña sin requerir la contraseña actual.
    Envía un correo notificando qué campos cambiaron (sin revelar la nueva contraseña).
    """
    data = request.get_json() or {}

    # Buscar usuario existente por ObjectId
    try:
        user = mongo.db.users.find_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "ID de usuario inválido"}), 400

    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404

    # Campos permitidos a actualizar y comparación
    updatable_fields = ["DNI", "name", "lastname", "email", "role"]
    updates = {}
    changed_fields = []

    for field in updatable_fields:
        if field in data and data[field] != user.get(field):
            updates[field] = data[field]
            changed_fields.append(field)

    # Manejo de cambio de contraseña si se proporciona nueva contraseña
    if "password" in data:
        # Hashear y preparar nueva contraseña
        updates["password"] = generate_password_hash(data["password"])
        # Notificar que contraseña cambió, sin revelar valor
        changed_fields.append("password")

    # Si no hay cambios, devolvemos sin modificar
    if not updates:
        return jsonify({"message": "Usuario sin cambios"}), 200

    # Aplicar actualización en MongoDB
    mongo.db.users.update_one({"_id": ObjectId(id)}, {"$set": updates})

    # Preparar y enviar correo de notificación
    # Excluir 'password' de la lista de campos mostrados
    email_fields = [f for f in changed_fields if f != "password"]
    user_after = mongo.db.users.find_one({"_id": ObjectId(id)})
    if user_after:
        email = user_after.get("email")
        name = user_after.get("name")
        lastname = user_after.get("lastname")

        # Crear mensaje usando la clase Message importada
        msg = Message(
            subject="Actualización de usuario",
            recipients=[email]
        )

        # Cuerpo del correo
        text_body = f"Hola {name} {lastname},\n\n" \
                    f"Se han actualizado los siguientes campos de tu cuenta: {', '.join(email_fields + ['contraseña'] if 'password' in changed_fields else email_fields)}.\n" \
                    "Si no reconoces estos cambios, contáctanos de inmediato.\n\nSaludos."
        html_body = f"<p>Hola {name} {lastname},</p>" \
                    f"<p>Se han actualizado los siguientes campos de tu cuenta: <strong>{', '.join(email_fields + ['contraseña'] if 'password' in changed_fields else email_fields)}</strong>.</p>" \
                    "<p>Si no reconoces estos cambios, contáctanos de inmediato.</p>" \
                    "<p>Saludos.</p>"

        msg.body = text_body
        msg.html = html_body
        # Enviar usando la extensión mail
        mail = current_app.extensions['mail']
        mail.send(msg)

    return jsonify({"message": "Usuario actualizado exitosamente"}), 200


@users_bp.route('/users/upload', methods=['POST'])
#@jwt_required()
def upload_users():
    if 'file' not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400

    file = request.files['file']
    fname = secure_filename(file.filename)
    if not fname.lower().endswith('.csv'):
        return jsonify({"error": "Sólo CSV permitido"}), 400

    # Leemos todo el CSV en memoria
    text = file.stream.read().decode('utf-8')
    stream = io.StringIO(text)
    # Si tu CSV NO trae cabecera, pásale fieldnames; si trae cabecera, quita fieldnames
    reader = csv.DictReader(stream,
                            fieldnames=['DNI','clave','lastname','name','email'],
                            delimiter=';'
                            )

    created = 0
    skipped = 0

    for row in reader:
        # usamos .get para no petar si la clave no existe
        dni       = row.get('DNI', '').strip()
        name      = row.get('name', '').strip()
        lastname  = row.get('lastname', '').strip()
        email     = row.get('email', '').strip()

        if not (dni and name and email):
            # fila incompleta → la saltamos
            continue

        if mongo.db.users.find_one({"DNI": dni}):
            skipped += 1
            continue

        pwd    = generate_random_password(12)
        hashed = generate_password_hash(pwd)

        mongo.db.users.insert_one({
            "DNI":        dni,
            "name":       name,
            "lastname":   lastname,
            "email":      email,
            "password":   hashed,
            "role":       "user"
        })

        # enviamos mail con credenciales
        msg = Message("Tus credenciales", recipients=[email])
        msg.body = f"Hola {name},\n\nDNI: {dni}\nPassword: {pwd}\n"
        mail.send(msg)

        created += 1

    return jsonify({"created": created, "skipped": skipped}), 200