Вы можете работать с картой MapGL JS API в проектах на React. Обратите внимание на следующие инструкции:

[Как добавить карту в приложение и избежать повторного рендеринга карты](https://docs.2gis.com/mapgl/start/react#prevent-rerender).[Как получить доступ к карте из другого компонента](https://docs.2gis.com/mapgl/start/react#access-from-other-components).

## Повторный рендеринг[](https://docs.2gis.com/mapgl/start/react#prevent-rerender)

Возьмём для примера простое приложение на React:

`import React from 'react';`

import ReactDOM from 'react-dom';


import { App } from './App';


const rootElement = document.getElementById('root');

ReactDOM.render(<App />, rootElement);



С простым компонентом App:

`import React from 'react';`


export const App = () => {

return <div>My App</div>;

};



Чтобы добавить в это приложение карту, создадим новый компонент:

`import { load } from '@2gis/mapgl';`


export const Map = () => {

useEffect(() => {

let map;

load().then((mapglAPI) => {

map = new mapglAPI.Map('map-container', {

center: [37.615655, 55.768005],

zoom: 13,

key: 'Your API access key',

});

});


// Удаляем карту при размонтировании компонента

return () => map && map.destroy();

}, []);


return (

<div style={{ width: '100%', height: '100%' }}>

<MapWrapper />

</div>

);

};



Обратите внимание, что в этом компоненте нет контейнера карты (`map-container`

). Чтобы избежать повторного рендеринга карты, мы создадим отдельный компонент, который будет использовать [React.memo](https://ru.reactjs.org/docs/react-api.html#reactmemo):

`const MapWrapper = React.memo(`

() => {

return <div id="map-container" style={{ width: '100%', height: '100%' }}></div>;

},

() => true,

);



Второй аргумент [React.memo](https://ru.reactjs.org/docs/react-api.html#reactmemo) — функция, которая определяет, можно ли использовать последний результат рендеринга, избегая таким образом повторного рендеринга. В нашем случае эта функция будет всегда возвращать `true`

.

Осталось добавить карту в компонент App и всё готово к работе:

`export const App = () => {`

return (

<div style={{ width: '100%', height: 400 }}>

<Map />

</div>

);

};



Полный исходный код можно найти в примере ниже.

## Получение доступа к карте[](https://docs.2gis.com/mapgl/start/react#access-from-other-components)

Второй частый сценарий использования: получение доступа к карте из другого компонента.

В качестве примера можно взять кнопку, которая меняет центр карты. Если эта кнопка будет расположена в отдельном компоненте, то нужно из этого компонента получить доступ к компоненту с картой. Для этого можно использовать [React Context API](https://ru.reactjs.org/docs/context.html).

Для начала создадим новый компонент и вызовем [React.createContext()](https://ru.reactjs.org/docs/context.html#reactcreatecontext), чтобы создать объект Context.

`const MapContext = React.createContext([undefined, () => {}]);`

const MapProvider = (props) => {

const [mapInstance, setMapInstance] = React.useState();


return (

<MapContext.Provider value={[mapInstance, setMapInstance]}>

{props.children}

</MapContext.Provider>

);

};



Затем обернём компонент App компонентом MapProvider. Это позволит использовать созданный объект Context в компоненте App и всех дочерних компонентах.

`ReactDOM.render(`

<MapProvider>

<App />

</MapProvider>,

rootElement,

);



Теперь после создания карты мы можем использовать Context, чтобы сохранить ссылку на карту:

`export const Map = () => {`

const [_, setMapInstance] = React.useContext(MapContext);


useEffect(() => {

let map;

load().then((mapglAPI) => {

map = new mapglAPI.Map('map-container', {

center: [37.615655, 55.768005],

zoom: 13,

key: 'Your API access key',

});


// Сохраняем ссылку на карту

setMapInstance(map);

});


// Удаляем карту при размонтировании компонента

return () => map && map.destroy();

}, []);


return (

<div style={{ width: '100%', height: '100%' }}>

<MapWrapper />

</div>

);

};



Сохранённую ссылку можно использовать в других компонентах приложения. Например, создадим кнопку, которая будет менять центр карты:

`export const MoveMapButton = () => {`

const [mapInstance] = React.useContext(MapContext);


const setInitialCenter = useCallback(() => {

if (mapInstance) {

mapInstance.setCenter([37.615655, 55.768005]);

}

}, [mapInstance]);


return <button onClick={setInitialCenter}>Set initial center</button>;

};



Полный исходный код можно найти в примере ниже.

Вы можете добавить пользовательский хук, который позволит выполнять `effect`

с сохранённой ранее ссылкой на карту:

`const useMapEffect = (`

// Функция, которая выполняется в useEffect при наличии mapInstance

effect,

// Зависимости, при изменении которых выполняется effect

deps,

) => {

const { mapInstance } = React.useContext(MapContext);


return React.useEffect(() => {

if (!mapInstance) {

return;

}


return effect({ mapInstance });

}, [mapInstance, ...deps]);

};



## Готовый пакет npm[](https://docs.2gis.com/mapgl/start/react#%D0%B3%D0%BE%D1%82%D0%BE%D0%B2%D1%8B%D0%B9-%D0%BF%D0%B0%D0%BA%D0%B5%D1%82-npm)

Если вы используете npm, вы можете скачать пакет [@2gis/mapgl](https://www.npmjs.com/package/@2gis/mapgl), который также включает поддержку TypeScript.

Примеры использования и другую информацию можно найти в [Readme](https://www.npmjs.com/package/@2gis/mapgl?activeTab=readme).

## Пример использования в стороннем проекте[](https://docs.2gis.com/mapgl/start/react#%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80-%D0%B8%D1%81%D0%BF%D0%BE%D0%BB%D1%8C%D0%B7%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F-%D0%B2-%D1%81%D1%82%D0%BE%D1%80%D0%BE%D0%BD%D0%BD%D0%B5%D0%BC-%D0%BF%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D0%B5)

См. пример использования MapGL в стороннем проекте в репозитории [github.com/city-mobil/frontend_react-2gis](https://github.com/city-mobil/frontend_react-2gis), где реализована React-обёртка. Также доступен npm-пакет обёртки: [react-2gis](https://www.npmjs.com/package/react-2gis).
