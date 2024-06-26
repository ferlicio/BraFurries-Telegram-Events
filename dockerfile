FROM python:3.8-slim-buster

WORKDIR /app

RUN pip3 install --upgrade pip && pip3 freeze > requirements.txt
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

## RUN mkdir -p /app/data

CMD ["python", "main.py"]