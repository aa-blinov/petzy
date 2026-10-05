import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button } from 'antd-mobile';
import { ChevronLeft } from 'lucide-react';
import { legalService, LEGAL_QUERY_KEY, type LegalInfo } from '../services/legal.service';
import { goBack } from '../utils/navigation';
import { LoadingSpinner } from '../components/LoadingSpinner';

/**
 * «Политика конфиденциальности» (/privacy) and «Согласие на обработку
 * персональных данных» (/consent), for users in Russia (152-ФЗ) and Kazakhstan
 * (Law No. 94-V). The consent is its own page: 152-ФЗ wants it apart from any
 * other document.
 *
 * Who the operator is, how to reach them and where the database server
 * stands come from the server (PRIVACY_* env, see web/legal.py). A change
 * of substance here needs PRIVACY_POLICY_VERSION bumped there, so everyone
 * is asked to agree again.
 */

const NOT_SET = 'пока не указан';

/** Where the data goes outside ``home``: the server's country (unless it is
    ``home`` itself), the file store, the error reports. */
function abroadFrom(home: string, info?: LegalInfo) {
  const server = info?.server_location?.trim();
  return [...(server && server.toLowerCase() !== home.toLowerCase() ? [server] : []), 'Нидерланды', 'Германия'];
}

const RU_LAW = 'Федеральный закон от 27.07.2006 № 152-ФЗ «О персональных данных»';
const KZ_LAW = 'Закон Республики Казахстан от 21.05.2013 № 94-V «О персональных данных и их защите»';

/** A version is its date, with «.2» and so on for a second wording that day. */
function formatVersion(version: string) {
  const date = new Date(`${version.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? version
    : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

/** «до 3 дней», «до 1 дня», «до 21 дня». */
function daysPhrase(n: number) {
  const lastTwo = n % 100;
  const last = n % 10;
  return `до ${n} ${last === 1 && lastTwo !== 11 ? 'дня' : 'дней'}`;
}

function Email({ address }: { address: string }) {
  return <a href={`mailto:${address}`}>{address}</a>;
}

/** «напишите на a@b.ru», or «напишите оператору» while no address is set. */
function WriteTo({ info, verb = 'напишите' }: { info?: LegalInfo; verb?: string }) {
  if (!info?.contact_email) return <>{verb} оператору</>;
  return (
    <>
      {verb} оператору на <Email address={info.contact_email} />
    </>
  );
}

function LegalPage({ title, children }: { title: string; children: (info?: LegalInfo) => ReactNode }) {
  const navigate = useNavigate();
  const { data: info, isPending, isError, refetch } = useQuery({
    queryKey: LEGAL_QUERY_KEY,
    queryFn: () => legalService.get(),
    staleTime: 60 * 60 * 1000,
  });

  return (
    <div className="legal-page">
      <article className="legal-page__body">
        <button type="button" className="legal-page__back" onClick={() => goBack(navigate, '/')}>
          <ChevronLeft size={18} strokeWidth={2} aria-hidden />
          Назад
        </button>
        <h1>{title}</h1>
        {info && <p className="legal-page__version">Редакция от {formatVersion(info.policy_version)}</p>}
        {info && !info.operator && (
          <p className="legal-page__notice">
            Владелец этого сервера ещё не указал, кто он и как с ним связаться. Пока этих данных нет, спросите о них того,
            кто пригласил вас в Petzy.
          </p>
        )}
        {/* Not before the facts arrive, and never without them: «пока не указан» for a second reads as the truth. A legal
            document drawn from a failed request is a document with the operator, the country and the retention period
            invented, so the failure is said outright instead. */}
        {isPending ? (
          <LoadingSpinner />
        ) : isError ? (
          <div className="legal-page__notice">
            <p role="alert">Не удалось загрузить документ. Проверьте соединение</p>
            <Button color="primary" fill="outline" onClick={() => void refetch()}>
              Повторить
            </Button>
          </div>
        ) : (
          children(info)
        )}
      </article>
    </div>
  );
}

export function PrivacyPolicy() {
  return (
    <LegalPage title="Политика конфиденциальности">
      {(info) => (
        <>
          <p>
            В Petzy ведут дневник здоровья питомца: кормление, вес, лекарства, документы. Здесь написано, какие данные о
            вас при этом хранятся, зачем, где и как их удалить.
          </p>
          <p>
            Политика действует для пользователей из России и Казахстана. Общие правила одни для всех, а там, где законы
            двух стран различаются, это написано отдельно.
          </p>

          <h2>Кто обрабатывает данные</h2>
          <p>
            Оператор персональных данных: {info?.operator || NOT_SET}.
            {info?.contact_email && (
              <>
                {' '}Вопросы о ваших данных присылайте на <Email address={info.contact_email} />.
              </>
            )}
          </p>

          <h2>Какие данные хранятся</h2>
          <ul>
            <li>Логин и пароль. Пароль хранится только в виде хеша, прочитать его нельзя.</li>
            <li>Имя и адрес почты, если вы их указали.</li>
            <li>
              Всё, что вы записываете о питомцах: карточки, фото, записи, лекарства, документы и сканы. Это данные о
              животном, но в документах бывают и ваши, например имя в счёте клиники.
            </li>
            <li>С кем вы делитесь питомцами и кто делится с вами.</li>
            <li>Если вы включили уведомления: адрес подписки вашего браузера и часовой пояс, чтобы напоминание пришло вовремя.</li>
            <li>IP-адрес и сведения о браузере: в журналах сервера и в отчётах об ошибках.</li>
          </ul>

          <h2>Зачем</h2>
          <ul>
            <li>Чтобы вы вели дневник и видели его с любого устройства.</li>
            <li>Чтобы входить в аккаунт и защищать его: ограничивать число попыток входа, завершать сеансы после смены пароля.</li>
            <li>Чтобы присылать письма, которые вы запросили: подтверждение почты, ссылку для нового пароля, предупреждение о смене пароля или почты.</li>
            <li>Чтобы напоминать о лекарствах и сроках документов, если вы включили уведомления.</li>
            <li>Чтобы вы могли делиться питомцем с другими людьми.</li>
            <li>Чтобы находить и исправлять ошибки в приложении.</li>
          </ul>
          <p>Рекламы в Petzy нет. Данные не продаются и не используются для рассылок или аналитики.</p>

          <h2>Основание</h2>
          <p>
            Ваше <Link to="/consent">согласие на обработку персональных данных</Link>, которое вы даёте при регистрации.
          </p>
          <ul>
            <li>В России: пункт 1 части 1 статьи 6 {RU_LAW.replace('Федеральный закон', 'Федерального закона')}.</li>
            <li>В Казахстане: {KZ_LAW}.</li>
          </ul>

          <h2>Где хранятся данные и кто их видит</h2>
          <ul>
            <li>База данных и само приложение работают на сервере. Страна, где он стоит: {info?.server_location || NOT_SET}.</li>
            <li>Фото, документы и резервные копии базы лежат в хранилище Backblaze B2 в Нидерландах.</li>
            <li>
              Отчёты об ошибках уходят в Sentry, в Германию. В отчёте есть логин, IP-адрес, адрес страницы и описание ошибки.
              Пароли, токены и cookies вырезаются из него до отправки.
            </li>
            <li>Письма отправляются через почтовый сервис, который подключил оператор.</li>
            <li>
              Уведомления доставляет служба push вашего браузера (Google, Apple, Mozilla или Microsoft). Текст
              уведомления зашифрован, служба его не видит.
            </li>
            <li>Люди, с которыми вы делитесь питомцем, видят его карточку, записи и ваш логин рядом с вашими записями.</li>
          </ul>
          <p>Часть данных хранится за границей, то есть передаётся в другие страны:</p>
          <ul>
            <li>для пользователей из России: {abroadFrom('Россия', info).join(', ')};</li>
            <li>для пользователей из Казахстана: {abroadFrom('Казахстан', info).join(', ')}.</li>
          </ul>
          <p>Больше данные никому не передаются, если этого не требует закон.</p>

          <h2>Сколько хранятся</h2>
          <ul>
            <li>Пока существует ваш аккаунт.</li>
            <li>
              После удаления аккаунта данные удаляются сразу. В резервных копиях базы они остаются ещё{' '}
              {daysPhrase(info?.backups_kept_days ?? 3)}, пока старые копии не заменятся новыми.
            </li>
            <li>Журналы сервера и отчёты об ошибках хранятся ограниченное время и удаляются автоматически.</li>
          </ul>

          <h2>Ваши права</h2>
          <ul>
            <li>Посмотреть свои данные: всё записанное видно в приложении, историю можно выгрузить в файл.</li>
            <li>Исправить их: записи и почту можно изменить в приложении, имя по вашему письму поменяет оператор.</li>
            <li>
              Удалить аккаунт: Настройки → «Удалить аккаунт». Питомцы, которыми вы делились, перейдут к тем, с кем вы ими
              делились. Остальное удалится.
            </li>
            <li>
              Отозвать согласие: удалите аккаунт или <WriteTo info={info} />. Без согласия Petzy не может
              хранить ваши данные, поэтому отзыв согласия означает удаление аккаунта.
            </li>
            <li>
              Узнать, как обрабатываются ваши данные: <WriteTo info={info} />. Ответ придёт в срок, который задаёт закон
              вашей страны.
            </li>
          </ul>
          <p>Если считаете, что ваши права нарушены, можно пожаловаться:</p>
          <ul>
            <li>
              в России: в Роскомнадзор или в суд. На запрос о ваших данных оператор отвечает в течение 10 рабочих дней;
            </li>
            <li>в Казахстане: в уполномоченный орган в сфере защиты персональных данных или в суд.</li>
          </ul>

          <h2>Cookies и хранилище браузера</h2>
          <p>
            Petzy ставит две cookie, без которых нельзя войти: access_token и refresh_token. Скрипты на странице их не
            видят. В хранилище браузера лежат настройки вроде темы и выбранного питомца. Рекламных и аналитических cookies
            нет.
          </p>

          <h2>Как данные защищены</h2>
          <p>
            Соединение зашифровано (HTTPS). Файлы открываются по ссылкам, которые работают несколько минут. Питомца видят
            только владелец и те, кого он пригласил.
          </p>

          <h2>Изменения</h2>
          <p>
            Новая редакция появляется на этой странице с новой датой. Если меняется что-то существенное, приложение
            попросит согласиться заново.
          </p>
        </>
      )}
    </LegalPage>
  );
}

export function PrivacyConsent() {
  return (
    <LegalPage title="Согласие на обработку персональных данных">
      {(info) => (
        <>
          <p>
            Регистрируясь в Petzy, я даю согласие оператору ({info?.operator || NOT_SET}
            {info?.contact_email && (
              <>
                , почта для обращений: <Email address={info.contact_email} />
              </>
            )}
            ) на обработку моих персональных данных на условиях ниже и{' '}
            <Link to="/privacy">политики конфиденциальности</Link>.
          </p>
          <p>
            Согласие даётся в соответствии с законом страны, где я живу: для России это {RU_LAW}, для Казахстана это{' '}
            {KZ_LAW}.
          </p>

          <h2>Какие данные</h2>
          <p>
            Логин, имя, адрес электронной почты, IP-адрес, сведения о браузере и устройстве, адрес push-подписки и часовой
            пояс, а также сведения обо мне в документах и записях, которые я добавляю.
          </p>

          <h2>Зачем</h2>
          <p>
            Работа дневника питомца на разных устройствах; вход в аккаунт и его защита; письма и напоминания, которые я
            запрашиваю; совместный доступ к питомцам; поиск и исправление ошибок.
          </p>

          <h2>Что с ними можно делать</h2>
          <p>
            Сбор, запись, систематизация, накопление, хранение, уточнение (обновление, изменение), извлечение,
            использование, передача (предоставление, доступ), блокирование, удаление, уничтожение. С использованием средств
            автоматизации и без них.
          </p>

          <h2>Кому передаются</h2>
          <p>
            Хостинг, где работают приложение и база данных: {info?.server_location || NOT_SET}. Backblaze, Inc.: хранение
            файлов и резервных копий, Нидерланды. Functional Software, Inc. (Sentry): отчёты об ошибках, Германия.
            Почтовый сервис оператора: отправка писем. Даю согласие на передачу данных в эти страны, в том числе на
            трансграничную передачу.
          </p>

          <h2>Срок и отзыв</h2>
          <p>
            Согласие действует, пока существует аккаунт или пока я его не отзову. Отозвать его можно, удалив аккаунт
            (Настройки → «Удалить аккаунт») или <WriteTo info={info} verb="написав" />. После отзыва данные
            удаляются, кроме тех, что закон требует хранить дольше.
          </p>
        </>
      )}
    </LegalPage>
  );
}
