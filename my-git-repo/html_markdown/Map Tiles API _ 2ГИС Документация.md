Сервис Map Tiles API предоставляет векторные тайлы для карт.

Для работы с векторными тайлами используйте JavaScript-библиотеку [MapGL JS API](https://docs.2gis.com/mapgl/overview/features) и размещайте на сайтах и в веб-приложениях трёхмерную интерактивную карту 2ГИС на WebGL-движке. При оформлении подписки на Map Tiles API безлимитный доступ к библиотеке MapGL JS API предоставляется бесплатно.

Также вы можете добавлять карты в мобильные приложения с помощью мобильных SDK для [iOS](https://docs.2gis.com/ios/sdk/overview), [Android](https://docs.2gis.com/android/sdk/overview) и [Flutter](https://docs.2gis.com/flutter/sdk/overview).

Прямая интеграция векторных тайлов без использования библиотеки или SDK 2ГИС не поддерживается.

## Начало работы[](https://docs.2gis.com/maps/others/maptiles/overview#getting-started)

### Получение ключа доступа[](https://docs.2gis.com/maps/others/maptiles/overview#getting-access-key)

- Зарегистрируйтесь в личном кабинете
[Менеджер Платформы](https://platform.2gis.ru/ru/?utm_source=docs&utm_medium=referral&utm_campaign=api_vector). - Создайте
[демо-ключ](https://docs.2gis.com/platform-manager/subscription/keys#demo)или купите[подписку](https://docs.2gis.com/platform-manager/subscription/purchase)для доступа к API. Подробнее о стоимости сервиса см. в разделе[Тарифы](https://docs.2gis.com/maps/others/maptiles/overview#tariffs).

Если у вас уже есть действующий API-ключ, полученный для MapGL JS API, вы можете использовать его для доступа к Map Tiles API до истечения срока действия подписки. Срок действия можно посмотреть в личном кабинете, на вкладке **Главная**.

Работать с ключами можно в Менеджере Платформы: подробнее см. в [документации личного кабинета](https://docs.2gis.com/platform-manager/overview).

### Интеграция библиотеки MapGL JS API[](https://docs.2gis.com/maps/others/maptiles/overview#using-mapgl-js-api)

MapGL JS API — это бесплатная JavaScript-библиотека для работы с трёхмерными интерактивными картами 2ГИС. Содержит готовый набор инструментов для взаимодействия с картой, автоматически запрашивает векторные тайлы и отображает их на странице.

Чтобы использовать с библиотекой MapGL JS API тайлы, предоставленные сервисом Map Tiles API, сначала получите ключ доступа, затем подключите библиотеку к вашему проекту. Подробнее см. в инструкции [Начало работы](https://docs.2gis.com/mapgl/start/first-steps).

### Пример использования[](https://docs.2gis.com/maps/others/maptiles/overview#%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80-%D0%B8%D1%81%D0%BF%D0%BE%D0%BB%D1%8C%D0%B7%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F)

## Статистика[](https://docs.2gis.com/maps/others/maptiles/overview#statistics)

При исчерпании лимитов сервис станет недоступен. Вы можете отслеживать расходование лимитов в подписке и статистику распределения запросов к сервису в личном кабинете. Подробнее об инструментах статистики см. в разделе [Статистика](https://docs.2gis.com/platform-manager/subscription/statistics#view-the-statistics).

## Тарифы[](https://docs.2gis.com/maps/others/maptiles/overview#tariffs)

- Стоимость сервиса рассчитывается исходя из количества запросов в месяц. Один запрос соответствует загрузке одного векторного тайла. Безлимитный доступ к библиотеке MapGL JS API предоставляется бесплатно.
- Актуальные тарифы можно посмотреть в
[Менеджере Платформы](https://platform.2gis.ru/ru/tariffs?utm_source=docs&utm_medium=referral&utm_campaign=api_vector).

## Варианты размещения[](https://docs.2gis.com/maps/others/maptiles/overview#distribution)

**Облако**: Map Tiles API доступен через публичные endpoint-ы 2ГИС.**On-Premise**: для получения векторных тайлов установите Tiles API в составе API-платформы 2ГИС в закрытом контуре. Подробнее см. в разделе[API-платформа для сервера](https://docs.2gis.com/on-premise/api-platform/overview).
