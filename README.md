# Buxta - Online Bookstore

An online bookstore platform built with Django, offering a comprehensive book management system and shopping experience.

## Features

- **Book Management**: Complete catalog with detailed book information
- **Shopping Cart**: Seamless shopping experience with cart functionality
- **Order Processing**: Handle orders and payments via WhatsApp integration
- **Admin Dashboard**: Comprehensive admin interface for:
    - Book/Author management
    - Category organization
    - Order processing
    - Customer management
    - Review moderation

## Project Structure

```
buxta/
├── manage.py
├── buxta/               # Project settings
├── home/               # Main application
│   ├── admin.py       # Admin interface
│   ├── models.py      # Database models
│   ├── views.py       # View logic
│   ├── urls.py        # URL routing
│   └── templates/     # HTML templates
└── user/              # User management app
```

## Requirements

- Python 3.8+
- Django 5.2+
- Other dependencies in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Paulmwas/buxta.git
cd buxta
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Usage

- Access the store at `http://localhost:8000`
- Admin dashboard at `http://localhost:8000/admin`
- Customer dashboard at `http://localhost:8000/dashboard`

## License

This project is licensed under the MIT License.