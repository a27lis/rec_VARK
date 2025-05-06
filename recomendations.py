import pandas as pd
from typing import List, Dict, Optional
from schemas import UserProfileSchema
from sqlalchemy import text


def prepare_data_for_recommender(input_df: pd.DataFrame) -> pd.DataFrame:
    result_df = pd.DataFrame({
        'resource_id': range(len(input_df)),  # Генерируем уникальные ID
        'title': input_df['title'],
        'link': input_df['link'],
        'description': input_df['description']
    })

    # Определяем соответствие между булевыми столбцами и текстовыми значениями
    style_mapping = {
        'learning_style_V': 'Визуал',
        'learning_style_A': 'Аудиал',
        'learning_style_R': 'Читатель/писатель',
        'learning_style_K': 'Кинестетик'
    }

    # Собираем активные стили обучения
    styles_list = []
    for style_col, style_text in style_mapping.items():
        styles_list.append(input_df[style_col].map({1: style_text, 0: ''}))

    # Объединяем стили через запятую, игнорируя пустые строки
    result_df['style_learning'] = pd.concat(styles_list, axis=1).apply(
        lambda x: ','.join(filter(None, x)),
        axis=1
    )

    # Определяем возрастную группу на основе бинарных столбцов
    def determine_age_group(row):
        groups = {
            'kid': row['age_group_kid'],
            'young': row['age_group_young'],
            'student': row['age_group_student'],
            'adult': row['age_group_adult'],
            'mature': row['age_group_mature']
        }
        return max(groups.items(), key=lambda x: x[1])[0]

    result_df['age_group'] = input_df.apply(determine_age_group, axis=1)

    return result_df

class EnhancedRecommendationSystem:
    def __init__(self):
        self.resources_df = None


    def load_data(self, db_session):
        """Загрузка данных из базы данных"""
        resources_query = """
           SELECT * FROM recomendations_resource
        """
        self.resources_df = pd.read_sql(resources_query, con=db_session.bind)
        input_data = self.resources_df

        # Преобразуем данные
        self.resources_df = prepare_data_for_recommender(input_data)

    def load_user(self, user_id: int, db_session) -> [UserProfileSchema]:

        """Получение профиля пользователя из базы данных"""
        query =text("""
                       SELECT 
                           u.age,
                           CONCAT(s.primary_style, ', ', s.secondary_style) as learning_styles
                       FROM users_user u
                       INNER JOIN survey_learningstyle s ON u.id = s.user_id
                       WHERE u.id = :user_id;
                   """)

        result = db_session.execute(query, {"user_id": user_id})
        row = result.fetchone()
        if row:
            data = {
                'age': row.age,
                'learning_styles': row.learning_styles.split(', ') if row.learning_styles else []
            }
            print(data)
            return data



    def calculate_user_profile(self, user_data: Dict) -> Dict:
        """Расчет профиля пользователя"""
        return {
            'learning_styles': user_data['learning_styles'],
            'age_group': self._get_age_group(user_data['age'])
        }

    def _get_age_group(self, age: int) -> str:
        """Определение возрастной группы"""
        if age < 10:
            return 'kid'
        elif age < 18:
            return 'young'
        elif age < 25:
            return 'student'
        elif age < 40:
            return 'adult'
        else:
            return 'mature'

    def calculate_resource_score(self, resource: pd.Series, user_profile: Dict) -> float:
        """Расчет релевантности ресурса для пользователя"""
        base_score = 0

        # Оценка на основе стилей обучения
        resource_styles = resource['style_learning'].split(',')
        user_styles = user_profile['learning_styles']

        # Проверяем, есть ли хотя бы один совпадающий стиль
        matching_styles = len(set(resource_styles) & set(user_styles))
        if matching_styles > 0:
            # Даем больше баллов, если совпадает больше стилей
            base_score += (matching_styles / len(user_styles)) * 75

        # Оценка на основе возрастной группы
        if resource['age_group'] == user_profile['age_group']:
            base_score += 25

        return min(base_score, 100)

    def get_recommendations(self, user_profile: Dict, n_recommendations: int = 5) -> List[Dict]:
        """Получение рекомендаций для пользователя"""
        recommendations = []
        for _, resource in self.resources_df.iterrows():
            score = self.calculate_resource_score(resource, user_profile)
            recommendations.append({
                'resource_id': resource['resource_id'],
                'title': resource['title'],
                'link': resource['link'],
                'description': resource['description'],
                'learning_styles': resource['style_learning'],
                'age_group': resource['age_group'],
                'relevance_score': score
            })

        # Сортировка и ограничение количества рекомендаций
        recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)
        return recommendations[:n_recommendations]