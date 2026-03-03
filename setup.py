from setuptools import setup, find_packages

setup(
    name="tender-intelligence-dashboard",
    version="1.0.0",
    description="Advanced Tender Intelligence Dashboard with AI capabilities",
    author="Tender Intelligence Team",
    author_email="info@tenderintelligence.com",
    packages=find_packages(),
    install_requires=[
        "Flask==2.3.3",
        "requests==2.31.0",
        "beautifulsoup4==4.12.2",
        "openrouter==0.1.1",
        "lxml==4.9.3",
        "gunicorn==21.2.0",
        "Werkzeug==2.3.7",
    ],
    entry_points={
        'console_scripts': [
            'tender-dashboard=app:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)