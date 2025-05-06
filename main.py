import logging
from typing import List, Optional, Dict, Any, Tuple
import json

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db
from recomendations import EnhancedRecommendationSystem
from schemas import UserProfileSchema, RecommendationResponse

import redis.asyncio as redis

app = FastAPI(
    title="Система рекомендаций",
    description="REST API для получения персонализированных рекомендаций",
    version="2.0.0"
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Конфигурация Redis
REDIS_HOST = "192.168.1.255"
REDIS_PORT = 6379
REDIS_DB = 0


@app.on_event("startup")
async def startup_event():
    """Инициализация подключения к Redis при запуске приложения"""
    global r

    try:
        # Создаем подключение к Redis
        r = redis.Redis(host='192.168.244.32', port=6379, db=0)

        # Проверяем соединение с Redis
        await r.ping()
        logger.info("Подключение к Redis успешно установлено")

        # Тестируем запись и чтение
        await r.set("test_key", "test_value")
        test_value = await r.get("test_key")
        logger.info(f"Тестовая запись успешно выполнена: {test_value}")

    except Exception as e:
        logger.error(f"Ошибка при подключении к Redis: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен"
        )

@app.on_event("shutdown")
async def shutdown_event():
    """Закрытие подключения к Redis при остановке приложения"""
    global r
    if r:
        await r.close()
        logger.info("Подключение к Redis закрыто")

@app.post("/recommendations/", response_model=List[RecommendationResponse])
async def get_recommendations(user_id: int, db: Session = Depends(get_db)):
    """
    Получение рекомендаций на основе профиля пользователя

    Args:
        user_id: id пользователя
        db: Сессия базы данных

    Returns:
        Список рекомендаций с оценками
    """
    recommender = EnhancedRecommendationSystem()
    recommender.load_data(db)
    data = recommender.load_user(user_id, db)

    print(user_id)

    recommendations = recommender.get_recommendations(
            recommender.calculate_user_profile(data)
        )
    json_str = json.dumps(recommendations)
    await r.set(f"user:{user_id}:recommendations", json_str)
    test_value = await r.get(f"user:{user_id}:recommendations")
    loaded_recommendations = json.loads(test_value.decode('utf-8'))
    logger.info(f"Запись успешно выполнена: {loaded_recommendations}")




    return recommendations





@app.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "healthy"}


@app.post("/recommendations/all/", response_model=Dict[str, Any])
async def calculate_all_recommendations(
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)

):
    """
    Расчёт рекомендаций для всех пользователей системы

    Args:
        background_tasks: task
        db: Сессия базы данных

    Returns:
        Статус операции и количество обработанных пользователей
    """
    recommender = EnhancedRecommendationSystem()
    recommender.load_data(db)

    query = text("""
                SELECT * FROM survey_learningstyle;
            """)
    # Получаем всех пользователей из базы данных
    users = db.execute(query).all()


    # Создаём задачу в фоновом режиме
    background_tasks.add_task(
        _process_all_users,
        recommender=recommender,
        users=users,
        db=db
    )

    return {"status": "processing", "message": "Расчёт рекомендаций запущен"}


async def _process_all_users(
        recommender: EnhancedRecommendationSystem,
        users: List[int],
        db: Session
):
    """
    Асинхронная обработка всех пользователей

    Args:

        recommender: Система рекомендаций
        users: Список ID пользователей
        db: Сессия базы данных
    """
    total_users = len(users)
    print(users)
    processed_count = 0

    for user_id in [user[7] for user in users]:
        try:
            # Загружаем данные пользователя
            data = recommender.load_user(user_id, db)

            # Получаем рекомендации
            recommendations = recommender.get_recommendations(
                recommender.calculate_user_profile(data)
            )

            # Сохраняем в Redis с TTL 24 часа
            await r.setex(
                f"user:{user_id}:recommendations",
                86400,  # 24 часа
                json.dumps(recommendations)
            )

            processed_count += 1

            # Логируем прогресс каждые 100 пользователей
            if processed_count % 100 == 0:
                logger.info(f"Обработано {processed_count}/{total_users} пользователей")

        except Exception as e:
            logger.error(f"Ошибка при обработке пользователя {user_id}: {str(e)}")

    logger.info(f"Завершено: обработано {processed_count}/{total_users} пользователей")