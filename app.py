#!flask/bin/python
from flask import Flask, request, render_template, Response, send_file
import requests
from bs4 import BeautifulSoup
import re
from youtube_transcript_api import YouTubeTranscriptApi
import zipfile
import io

app = Flask(__name__)

# When the webpage is executed, it will be directed to index.html.
@app.route('/')  # ['POST','GET'])
def go_home():
    return render_template('index.html')


#  Retrieve the titles of YouTube videos.
def get_video_info(url):
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
    title = soup.title.string
    return title

# Shorten the text and remove any characters not allowed in the file.
def clean_title(title):
    # Remove "feat"、"ft" and everything follows it
    title = re.split('feat|ft|YouTube|Youtube', title, flags=re.IGNORECASE)[0]
    # Remove "|", "｜", "-" and everything follows it
    title = re.split('[|｜-]', title)[0]
    # Remove or Replace characters that are not allowed in file names. 
    title = (title.replace("?", "？")
                 .replace("/", " ")
                 .replace(":", " -")
                 .replace("*", "")
                 .replace("<", "")
                 .replace(">", ""))
    # Finally, strip leading/trailing white spaces
    title = title.strip()
    return title


# 在index.html按下submit時，會取得前端傳來的url，並回傳結果
@app.route('/', methods=['GET','POST'])
def submit():
    url = request.form.get('url')
    # Check if the URL is correct.
    try:
        video_title = get_video_info(url)
        print(f'Title: {video_title}')
        video_id = url.split('watch?v=')[1]
    except Exception:
        video_id = None
        # print('URL is incorrect. Please enter the correct YouTube video URL!')
        return render_template('result3.html')
    
    # Check if subtitles exist for the video.
    is_transcript_exist = True
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except Exception:
        is_transcript_exist = False
        if video_id != None:
            # print("No transcript found for this video.")  
            return render_template('result2.html', title=video_title, web_url=url)
    
    # The video has subtitles.
    if is_transcript_exist == True:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript_info = str(transcript_list)
        # print(transcript_info)

        # Find out which manually created subtitles are available.
        match_manually_created = re.search(r'\(MANUALLY CREATED\)\n((?: - .*\n)*)', transcript_info)
        if match_manually_created:
            cc_manually_created_list = re.findall(r' - (.*?) \(', match_manually_created.group(1))

        # Find out which generated subtitles are available.
        match_generated = re.search(r'\(GENERATED\)\n - (.*?) \(', transcript_info)
        if match_generated:
            cc_generated = match_generated.group(1)

        cc_type_list = cc_manually_created_list
        if match_generated != None:
            cc_type_list.append(cc_generated)
        # print("Languages: ", cc_type_list)

        cc_list_str = "; ".join(cc_type_list)
        cc_default = str(cc_type_list[0])

        return render_template('download.html', title=video_title, web_url=url,  cc_list=cc_type_list, cc_list_str=cc_list_str, cc_default=cc_default)


# 列出所有可供下載的字幕讓使用者選擇
@app.route('/download/', methods=['GET','POST'])
def download():
    url = request.form.get('web_url')
    video_id = url.split('watch?v=')[1]
    video_title = get_video_info(url)
    cc_type = request.form.get('cc_type')  # Get the selected language from the form.
    cc_list_str = request.form.get('cc_list')
    cc_list = eval(cc_list_str)

    # Download the selected language subtitles.
    if (cc_type != 'All') or (cc_type == 'All' and len(cc_list)==1):
        if cc_type == 'All':
            cc_type = cc_list[0] 
        try:
            Translation_Languages =  [f'{cc_type}']  # eg.'zh-TW', 'zh'
            subtitle = YouTubeTranscriptApi.get_transcript(video_id, languages=Translation_Languages)
        except Exception:
            # print('The selected language does not have subtitles available.')
            return render_template('result4.html', title=video_title, web_url=url)
        text_all = ""
        text_subtitle = " \n".join([sub['text'] for sub in subtitle])
        text_all = text_all + f"Title: {video_title}\nUrl: {url}\n\n" 
        text_all = text_all + text_subtitle + "\n\n----------\n"
        # ===== download the file =====
        title = clean_title(video_title)
        file_name = f'{title}_{cc_type}.txt'
        # with open(file_name, 'w', encoding='utf-8') as file:
        #     file.write(text_all)
        response = Response(text_all, mimetype='text/csv')
        response.headers["Content-Disposition"] = f"attachment; filename={file_name.encode().decode('latin-1')}"
        # ============================= 
        return response
        # return render_template('result.html', title=video_title, web_url=url, subtitle_all=text_subtitle, cc_type=cc_type)
    
    # Download subtitles for all languages.
    if (cc_type == 'All' and len(cc_list)>1):
        # Initiate a BytesIO buffer to save all subtitles files
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for cc in cc_list:
                try:
                    Translation_Languages = [f'{cc}']
                    subtitle = YouTubeTranscriptApi.get_transcript(video_id, languages=Translation_Languages)
                except Exception:
                    # If the language does not have subtitles available, skip it.
                    continue
                text_all = ""
                text_subtitle = " \n".join([sub['text'] for sub in subtitle])
                text_all = text_all + f"Title: {video_title}\nUrl: {url}\n\n"
                text_all = text_all + text_subtitle + "\n\n----------\n"
                # Add the file to the ZIP
                title = clean_title(video_title)
                file_name = f'{title}_{cc}.txt'
                zf.writestr(file_name, text_all)
        # Finish the zip file
        mem_zip.seek(0)
        response = Response(mem_zip, mimetype='application/zip')
        title = clean_title(video_title)
        file_name = f'{title}.zip'
        response.headers["Content-Disposition"] = f"attachment; filename={file_name.encode().decode('latin-1')}"
        return response


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
