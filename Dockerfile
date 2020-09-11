FROM python:3.8

RUN mkdir -p /usr/src/app/

WORKDIR /usr/src/app/

COPY . /usr/src/app/

RUN pip install --no-cache-dir -r requirements.txt

ENV TZ=Europe/Kiev

CMD ["python", "bot.py"]