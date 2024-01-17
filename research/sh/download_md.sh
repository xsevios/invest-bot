figi_list=figi.txt
token="t.F-iravnXHCrMSTMV1qFA4H3nnR72VDJvSkjmxGu72dd6ULoVuvKQeqsUGnPCAyvd4s5CU34Sd6OSlsrZCF6H-Q"
minimum_year=2017
current_year=$(date +%Y)
url=https://invest-public-api.tinkoff.ru/history-data
function download {
  local figi=$1
  local year=$2
  local data_dir=$3

  # выкачиваем все архивы с текущего до 2004 года
  if [ "$year" -lt "$minimum_year" ]; then
    return 0
  fi

  local file_name=${data_dir}/${figi}_${year}.zip
  echo "downloading $figi for year $year"
  local response_code=$(curl -s --location "${url}?figi=${figi}&year=${year}" \
      -H "Authorization: Bearer ${token}" -o "${file_name}" -w '%{http_code}\n')

  # Если превышен лимит запросов в минуту (30) - повторяем запрос.
  if [ "$response_code" = "429" ]; then
      echo "rate limit exceed. sleep 5"
      sleep 5
      download "$figi" "$year";
      return 0
  fi
  # Если невалидный токен - выходим.
  if [ "$response_code" = "401" ] || [ "$response_code" = "500" ]; then
      echo 'invalid token'
      exit 1
  fi
  # Если данные по инструменту за указанный год не найдены.
  if [ "$response_code" = "404" ] || [ "$response_code" = "400" ]; then
      echo "data not found for figi=${figi}, year=${year}, removing empty file"
      # Удаляем пустой архив.
      rm -rf $file_name
  elif [ "$response_code" != "200" ]; then
      # В случае другой ошибки - просто напишем ее в консоль и выйдем.
      echo "unspecified error with code: ${response_code}"
      exit 1
  fi

  ((year--))
  download "$figi" "$year" "$data_dir";
}

while read -r figi; do
data_dir=zip/${figi}
mkdir -p "$data_dir"
download "$figi" "$current_year" "$data_dir"
done < ${figi_list}