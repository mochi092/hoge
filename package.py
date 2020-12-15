# -*- coding: utf-8 -*-
import commands
import csv
import os
import sys
import traceback

from PIL import Image, ImageDraw, ImageFont
import common as cmn


def create_watermark(watermark, output_dir, kid):
    output_file = '%s_watermark.png' % kid

    font = u'./fonts/%s' % cmn.WATERMARK_FONT
    fontsize = 20  # 透かし文字の大きさ
    opacity = 255  # 透かし文字の透明度
    color = (0, 0, 0)  # 透かし文字の色

    # フォントイメージを作成し、幅と高さを取得
    im = Image.new('RGBA', (500, 100), (255, 255, 255, 0))
    draw = ImageDraw.Draw(im)
    fnt = ImageFont.truetype(font=font, size=fontsize, encoding='UTF-8')
    fontw, fonth = draw.textsize(watermark, font=fnt)

    # 取得した幅と高さのRGBAイメージを作成し、フォントを書き込む
    im = Image.new('RGBA', (fontw, fonth), (255, 255, 255, 0))
    draw = ImageDraw.Draw(im)
    textw, texth = draw.textsize(watermark, font=fnt)
    draw.text(((fontw - textw) / 2, (fonth - texth) / 2), watermark, font=fnt, fill=color + (opacity,))

    im.save('%s/%s' % (output_dir, output_file))
    return output_file


def put_watermark(video_file, output_dir, watermark_file, kid):
    output_file = '%s_wm.mp4' % kid
    im = Image.open(output_dir + '/' + watermark_file)
    x, y = im.size
    cmd = \
        'ffmpeg ' + \
        '-y ' + \
        '-c:v h264_cuvid ' + \
        '-i %s ' % video_file + \
        '-vf "movie=%s [watermark];[in][watermark] overlay=main_w-overlay_w-120:main_h-overlay_h-5 [out]" ' % (
                output_dir + '/' + watermark_file) + \
        '-c:v h264_nvenc ' + \
        '%s' % (output_dir + '/' + output_file)
    print '---------------------------------------'
    print "ウォータマーク埋め込みをおこないます"
    print cmd
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        print output
        raise Exception('ウォータマーク埋め込みに失敗しました')
    return output_file


def put_watermark2(video_file, output_dir, watermark_file, kid):
    output_file = '%s_wm.mp4' % kid
    im = Image.open(output_dir + '/' + watermark_file)
    x, y = im.size
    cmd = \
        'ffmpeg ' + \
        '-y ' + \
        '-i %s ' % video_file + \
        '-i %s ' % (output_dir + '/' + watermark_file) + \
        '-filter_complex "[1]format=yuva420p,lut=a=\'val*0.8\'[a];[0][a] overlay=(W-w)-%d:(H-h)-%d" ' % (x / 2, y / 2) + \
        '-movflags +faststart ' + \
        '-pix_fmt yuv420p ' + \
        '-c:v libx264 ' + \
        '%s' % (output_dir + '/' + output_file)
    print '---------------------------------------'
    print "ウォータマーク埋め込みをおこないます"
    print cmd
    print commands.getoutput(cmd)
    return output_file


def fragment_video(watermarked_video_file, output_dir, kid):
    output_file = '%s_frag.mp4' % kid
    cmd = \
        'mp4fragment ' + \
        '%s ' % (output_dir + '/' + watermarked_video_file) + \
        '%s' % (output_dir + '/' + output_file)
    print '---------------------------------------'
    print "フラグメント化をおこないます"
    print cmd
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        print output
        raise Exception('フラグメント化に失敗しました')
    return output_file


def convert_mpegdash(fragmented_video_file, output_dir, kid, key, exec_dir='/usr/local/bin', is_encrypt=True):
    converted_video_output = '%s/output' % output_dir

    # 既存のディレクトリを削除
    commands.getoutput('rm -rf %s' % converted_video_output)
    if is_encrypt:
        cmd = \
            'mp4dash ' + \
            '--use-segment-timeline ' + \
            '--exec-dir=%s ' % exec_dir + \
            '--encryption-key=%s:%s ' % (kid, key) + \
            '--encryption-args="--global-option mpeg-cenc.eme-pssh:true" ' + \
            '--output-dir=%s ' % converted_video_output + \
            '%s' % (output_dir + '/' + fragmented_video_file)
    else:
        cmd = \
            'mp4dash ' + \
            '--use-segment-timeline ' + \
            '--exec-dir=%s ' % exec_dir + \
            '--output-dir=%s ' % converted_video_output + \
            '%s' % (output_dir + '/' + fragmented_video_file)
    print '---------------------------------------'
    print "MPEG-DASH化をおこないます"
    print cmd
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        print output
        raise Exception('MPEG-DASH化に失敗しました')
    return converted_video_output


def archive_video(converted_video_output, output_dir, video_file, kid):
    cmd = 'mv %s/thumbnail.jpg %s/output' % (cmn.ENCODE_DIR, cmn.PACKAGE_DIR)
    (status, output) = commands.getstatusoutput(cmd)

    output_file = cmn.create_archive_filename(video_file, kid)
    cmd = 'cd %s; zip %s -r %s' % (output_dir, output_file, os.path.basename(converted_video_output))
    print '---------------------------------------'
    print "アーカイブをおこないます"
    print cmd
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        print output
        raise Exception('アーカイブ化に失敗しました')
    return output_file


def cleanup(output_dir, watermark_file, watermarked_video, fragmented_video, converted_video_output):
    print commands.getoutput('rm -rf %s' % (output_dir + '/' + watermark_file))
    print commands.getoutput('rm -rf %s' % (output_dir + '/' + watermarked_video))
    print commands.getoutput('rm -rf %s' % (output_dir + '/' + fragmented_video))
    print commands.getoutput('rm -rf %s' % (output_dir + '/' + os.path.basename(converted_video_output)))


def process(video, name, mail):
    try:

        video_file = cmn.ENCODE_DIR + '/' + video  # コマンドライン引数
        kid = cmn.create_kid(mail)
        key = cmn.create_key(mail)

        # kid = hashlib.md5(mail).hexdigest()
        # key = hashlib.md5(mail + 'CAFEBABE').hexdigest()
        # name = args[2].decode('UTF-8')  # コマンドライン引数から受け取る
        # mail = args[3].decode('UTF-8')  # コマンドライン引数から受け取る

        output_dir = cmn.PACKAGE_DIR

        print '------------------------------------------'
        print 'package.pyが取得した情報'
        print 'video:%s' % video_file
        print 'output_dir:%s' % output_dir
        print 'name:%s' % name
        print 'mail:%s' % mail
        print 'kid:%s' % kid
        print 'key:%s' % key

        # 出力先を作成
        if not os.path.exists(output_dir):
            cmd = 'mkdir -p %s' % output_dir
            commands.status(cmd)

        # ウォーターマーク文字列を作成
        watermark = '%s(%s)' % (name.decode('utf-8'), mail)

        # パッケージ化
        watermark_file = create_watermark(watermark, output_dir, kid)
        watermarked_video = put_watermark(video_file, output_dir, watermark_file, kid)
        fragmented_video = fragment_video(watermarked_video, output_dir, kid)
        converted_video_output = convert_mpegdash(fragmented_video, output_dir, kid, key, is_encrypt=True)
        archived_video = archive_video(converted_video_output, output_dir, video_file, kid)
        cleanup(output_dir, watermark_file, watermarked_video, fragmented_video, converted_video_output)

    except Exception as e:
        print e
        print traceback.format_exc()


if __name__ == '__main__':
    try:
        args = sys.argv

        if len(args) == 4:
            video = args[1]
            mail = args[2]
            name = args[3]
            process(video, name, mail)
        elif len(args) == 3 and args[1] == '-f':
            input_csv_file = cmn.CSV_DIR + '/' + args[2]
            if os.path.exists('%s' % input_csv_file):
                with open(input_csv_file) as f:
                    reader = csv.reader(f)
                    for row in reader:
                        video = row[0]
                        mail = row[1]
                        name = row[2]
                        process(video, name, mail)
            else:
                print '指定したファイルが見つかりません'
        else:
            print '引数が正しくありません'

    except Exception as e:
        print e
        print traceback.format_exc()
